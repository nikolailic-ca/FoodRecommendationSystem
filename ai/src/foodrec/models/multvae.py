"""Mult-VAE and Mult-DAE (Liang et al., WWW 2018) - the served model.

Both share this file; `variational=False` is the denoising autoencoder:

    Mult-DAE : n_items -> 200 -> n_items, tanh, dropout 0.5, weight decay 1e-4
    Mult-VAE : n_items -> 600 -> (mu, logvar of 200) -> 600 -> n_items

Three details decide whether this works at all, and all three were wrong at some
point in the exploratory notebooks:

  1. the input row is L2-normalised BEFORE dropout, and the multinomial
     log-likelihood is taken against that same normalised row (as in the
     reference implementation);
  2. the loss is a multinomial log-likelihood over the softmax of the whole
     catalog, not a per-item binary cross-entropy;
  3. at evaluation time dropout is off and the latent code is mu, never a sample
     - otherwise the metrics wobble by a point between runs.

MPS has no sparse tensors and no float64, so every batch is densified in numpy
first and moved to the device as float32.  With --device cpu the run is bit
reproducible for a given seed.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch
from scipy.sparse import csr_array
from torch import nn
from torch.nn import functional as F

from foodrec.metrics import evaluate_ranking
from foodrec.models.base import BaseModel, as_binary_csr


class MultVAENet(nn.Module):
    """Encoder/decoder pair.  Layer names are part of the export contract."""

    def __init__(self, n_items: int, hidden: int = 600, latent: int = 200,
                 dropout: float = 0.5, variational: bool = True) -> None:
        super().__init__()
        self.n_items = n_items
        self.hidden = hidden
        self.latent = latent
        self.variational = variational
        self.dropout = nn.Dropout(dropout)

        if variational:
            self.enc_1 = nn.Linear(n_items, hidden)
            self.enc_2 = nn.Linear(hidden, 2 * latent)
            self.dec_1 = nn.Linear(latent, hidden)
            self.dec_2 = nn.Linear(hidden, n_items)
        else:
            self.enc_1 = nn.Linear(n_items, latent)
            self.dec_2 = nn.Linear(latent, n_items)

        self.reset_parameters()

    def reset_parameters(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.normal_(module.bias, std=0.001)

    def encode(self, x_norm: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor | None]:
        h = self.dropout(x_norm)
        h = torch.tanh(self.enc_1(h))
        if not self.variational:
            return h, None
        h = self.enc_2(h)
        mu, logvar = h[:, : self.latent], h[:, self.latent :]
        return mu, logvar

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        if self.variational:
            z = torch.tanh(self.dec_1(z))
        return self.dec_2(z)

    def forward(self, x_norm: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        mu, logvar = self.encode(x_norm)
        if not self.variational:
            return self.decode(mu), torch.zeros((), device=x_norm.device)
        if self.training:
            std = torch.exp(0.5 * logvar)
            z = mu + std * torch.randn_like(std)
        else:
            z = mu  # deterministic at evaluation time
        kl = -0.5 * torch.mean(torch.sum(1 + logvar - mu.pow(2) - logvar.exp(), dim=1))
        return self.decode(z), kl


def _normalise(dense: np.ndarray) -> np.ndarray:
    norm = np.sqrt((dense * dense).sum(axis=1, keepdims=True))
    np.maximum(norm, 1e-9, out=norm)
    return dense / norm


class MultVAE(BaseModel):
    key = "multvae"
    display_name = "Mult-VAE"
    supports_strong = True
    score_batch_size = 500

    def __init__(self, n_items: int, variational: bool = True, hidden: int = 600,
                 latent: int = 200, dropout: float = 0.5, lr: float = 1e-3,
                 weight_decay: float | None = None, batch_size: int = 500,
                 max_epochs: int = 100, patience: int = 10, beta: float = 0.2,
                 anneal_epochs: int = 20, val_sample: int = 10000):
        super().__init__(n_items)
        self.variational = variational
        if not variational:
            self.key = "multdae"
            self.display_name = "Mult-DAE"
        self.hidden = hidden
        self.latent = latent
        self.dropout = dropout
        self.lr = lr
        # weight decay 1e-4 for the DAE (no KL term to regularise it), 0 for the VAE
        self.weight_decay = (1e-4 if not variational else 0.0) if weight_decay is None else weight_decay
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.beta = beta
        self.anneal_epochs = anneal_epochs
        self.val_sample = val_sample
        self.net: MultVAENet | None = None
        self.device = torch.device("cpu")

    # ------------------------------------------------------------------ train

    def _build(self, device: torch.device) -> MultVAENet:
        net = MultVAENet(self.n_items, self.hidden, self.latent, self.dropout, self.variational)
        return net.to(device)

    def fit(self, train, *, val_input=None, val_target=None, val_users=None,
            seed=42, device="cpu", verbose=True, max_epochs=None):
        torch.manual_seed(seed)
        binary = as_binary_csr(train)
        device = torch.device(device) if isinstance(device, str) else device
        self.device = device
        self.net = self._build(device)

        optimiser = torch.optim.Adam(
            self.net.parameters(), lr=self.lr, weight_decay=self.weight_decay
        )

        active_users = np.flatnonzero(np.diff(binary.indptr) > 0).astype(np.int64)
        n_batches = max(1, int(np.ceil(active_users.shape[0] / self.batch_size)))
        anneal_steps = max(1, self.anneal_epochs * n_batches)

        fixed_epochs = max_epochs is not None
        total_epochs = max_epochs if fixed_epochs else self.max_epochs
        do_validation = (not fixed_epochs) and val_target is not None and val_users is not None

        eval_users = None
        if do_validation:
            eval_users = np.asarray(val_users, dtype=np.int64)
            if eval_users.shape[0] > self.val_sample:
                rng = np.random.default_rng(seed)
                eval_users = np.sort(rng.choice(eval_users, self.val_sample, replace=False))

        best_score = -np.inf
        best_state: dict | None = None
        best_epoch = 0
        stale = 0
        step = 0
        started = time.perf_counter()

        for epoch in range(1, total_epochs + 1):
            self.net.train()
            order = np.random.default_rng(seed + epoch).permutation(active_users)
            epoch_loss = 0.0
            for start in range(0, order.shape[0], self.batch_size):
                rows = order[start : start + self.batch_size]
                dense = _normalise(binary[rows].toarray().astype(np.float32))
                x = torch.from_numpy(dense).to(device)

                beta_t = min(self.beta, self.beta * step / anneal_steps) if self.variational else 0.0
                logits, kl = self.net(x)
                neg_ll = -torch.mean(torch.sum(F.log_softmax(logits, dim=1) * x, dim=1))
                loss = neg_ll + beta_t * kl

                optimiser.zero_grad(set_to_none=True)
                loss.backward()
                optimiser.step()
                epoch_loss += float(loss.detach().cpu()) * rows.shape[0]
                step += 1

            epoch_loss /= max(1, order.shape[0])
            record = {"epoch": epoch, "loss": round(epoch_loss, 5),
                      "beta": round(min(self.beta, self.beta * step / anneal_steps), 5)}

            if do_validation:
                metrics = evaluate_ranking(
                    self.scorer(val_input),
                    mask=val_input,
                    target=val_target,
                    users=eval_users,
                    ks=(20,),
                    coverage_k=20,
                    batch_size=self.score_batch_size,
                )
                score = metrics["ndcg@20"]
                record["val_ndcg@20"] = score
                if score > best_score + 1e-6:
                    best_score = score
                    best_epoch = epoch
                    best_state = {k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()}
                    stale = 0
                elif self.variational and epoch <= self.anneal_epochs:
                    # Do not count the KL annealing phase towards patience.  While
                    # beta ramps, validation NDCG@20 reliably DIPS (measured on
                    # Food.com: 0.0184 at epoch 1 -> 0.0159 at epoch 11 -> 0.0191 at
                    # epoch 21, once beta caps).  The dip is longer than a patience
                    # of 10, so the run would always be killed before the model
                    # reaches the regime it was designed for.
                    pass
                else:
                    stale += 1
            self.history.append(record)

            if verbose:
                suffix = f"  val NDCG@20={record.get('val_ndcg@20', float('nan')):.4f}" if do_validation else ""
                print(f"    epoha {epoch:>3}/{total_epochs}  loss={epoch_loss:8.3f}{suffix}")

            if do_validation and stale >= self.patience:
                if verbose:
                    print(f"    rano zaustavljanje na epohi {epoch} (najbolja: {best_epoch})")
                break

        if best_state is not None:
            self.net.load_state_dict(best_state)
        self.net.to(device)
        self.best_epoch = best_epoch if do_validation else total_epochs
        self.train_time_s = time.perf_counter() - started
        return self

    # ------------------------------------------------------------------ score

    @torch.no_grad()
    def score_users(self, rows, X_input):
        rows = np.asarray(rows, dtype=np.int64)
        self.net.eval()
        dense = _normalise(csr_array(X_input)[rows].toarray().astype(np.float32))
        x = torch.from_numpy(dense).to(self.device)
        mu, _ = self.net.encode(x)  # dropout is off in eval mode
        logits = self.net.decode(mu)
        return logits.detach().to("cpu").numpy().astype(np.float32)

    def hyperparams(self) -> dict:
        return {
            "variational": self.variational,
            "hidden": self.hidden,
            "latent": self.latent,
            "dropout": self.dropout,
            "lr": self.lr,
            "weight_decay": self.weight_decay,
            "batch_size": self.batch_size,
            "max_epochs": self.max_epochs,
            "patience": self.patience,
            "beta": self.beta if self.variational else 0.0,
            "anneal_epochs": self.anneal_epochs if self.variational else 0,
            "loss": "multinomial log-likelihood" + (" + beta * KL" if self.variational else ""),
        }

    def _save_arrays(self, directory: Path) -> None:
        torch.save(self.net.state_dict(), directory / "model.pt")

    @classmethod
    def _load_arrays(cls, directory: Path, meta: dict) -> MultVAE:
        hyper = meta.get("hyperparams", {})
        model = cls(
            meta["n_items"],
            variational=hyper.get("variational", True),
            hidden=hyper.get("hidden", 600),
            latent=hyper.get("latent", 200),
            dropout=hyper.get("dropout", 0.5),
            lr=hyper.get("lr", 1e-3),
            weight_decay=hyper.get("weight_decay"),
            batch_size=hyper.get("batch_size", 500),
            max_epochs=hyper.get("max_epochs", 100),
            patience=hyper.get("patience", 10),
            beta=hyper.get("beta", 0.2),
            anneal_epochs=hyper.get("anneal_epochs", 20),
        )
        model.net = MultVAENet(
            meta["n_items"], model.hidden, model.latent, model.dropout, model.variational
        )
        state = torch.load(directory / "model.pt", map_location="cpu", weights_only=True)
        model.net.load_state_dict(state)
        model.net.eval()
        model.device = torch.device("cpu")
        return model


class MultDAE(MultVAE):
    """Mult-DAE: the same file with the stochastic layer removed."""

    key = "multdae"
    display_name = "Mult-DAE"

    def __init__(self, n_items: int, **kwargs):
        kwargs.setdefault("hidden", 600)
        kwargs.setdefault("latent", 200)
        kwargs["variational"] = False
        super().__init__(n_items, **kwargs)
