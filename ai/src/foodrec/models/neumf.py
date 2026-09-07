"""NeuMF - Neural Collaborative Filtering (He et al., WWW 2017).

GMF branch (dim 32) and an MLP branch (32+32 embeddings -> 64 -> 32 -> 16 -> 8)
concatenated into a single logit, trained with binary cross-entropy against 4
uniformly sampled negatives per positive, resampled every epoch.

Two properties matter for the thesis and are reported, not hidden:

  * NO PRETRAINING.  The original paper initialises NeuMF from separately
    trained GMF and MLP models; here both branches are trained from scratch,
    which is a deliberate simplification and costs some accuracy.
  * It cannot serve a user it never saw.  Scoring needs an embedding row indexed
    by user id, so the strong-generalization view is reported as N/A.  That is
    the cold-start argument for choosing Mult-VAE as the served model.

Full-catalog scoring is O(n_items x MLP) per user, so users are scored in small
batches (32).  Next to a single Mult-VAE forward pass this is orders of
magnitude more expensive - measured and reported in ai/results/summary.md.

The embedding width defaults to 8, not the paper's 32.  At 32 the model carries
4.2 million embedding parameters against 540k training interactions, peaks at
epoch 3 and then overfits; at 8 it carries 1.05 million, trains for 5 epochs and
scores better (validation NDCG@20 0.0193 vs 0.0190).  Weight decay is left at 0
on purpose: Adam decay on embedding tables that each receive a handful of
gradient updates drives every row to zero, and 1e-4 collapsed the model to random
ranking (Recall@20 0.0005 against a 0.0005 floor).
"""

from __future__ import annotations

import itertools
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from foodrec.metrics import evaluate_ranking
from foodrec.models.base import BaseModel, as_binary_csr

# Upper bound on (user, item) pairs pushed through the MLP in one shot.
_ROW_BUDGET = 2_000_000


#: Narrowest the tower is allowed to get.  Below this a ReLU layer reliably dies.
MIN_TOWER_WIDTH = 8


def default_layers(mlp_dim: int) -> tuple[int, ...]:
    """Tower widths for a given embedding size: 2d -> d -> d/2 -> d/4, floored at 8.

    The first entry MUST be 2 * mlp_dim, because the tower is fed
    cat([mlp_user, mlp_item]).  With mlp_dim=32 this reproduces the paper's
    (64, 32, 16, 8); sweeping the embedding down has to shrink the tower with it.

    The floor is not cosmetic.  Halving all the way down gives (16, 8, 4, 2) at
    mlp_dim=8, and that 2-unit final ReLU dies: measured on Food.com, 100% of the
    tower's output slots were zero after training, the MLP branch contributed
    exactly 0.000 to the logit against GMF's 0.552, and the model had silently
    degenerated into plain GMF.  Sweeping the embedding down would then not be
    measuring a smaller NeuMF at all.
    """
    return tuple(max(MIN_TOWER_WIDTH, 2 * mlp_dim // 2**i) for i in range(4))


class NeuMFNet(nn.Module):
    def __init__(
        self,
        n_users: int,
        n_items: int,
        gmf_dim: int = 32,
        mlp_dim: int = 32,
        layers: tuple[int, ...] | None = None,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        layers = tuple(layers) if layers else default_layers(mlp_dim)
        self.gmf_user = nn.Embedding(n_users, gmf_dim)
        self.gmf_item = nn.Embedding(n_items, gmf_dim)
        self.mlp_user = nn.Embedding(n_users, mlp_dim)
        self.mlp_item = nn.Embedding(n_items, mlp_dim)

        tower: list[nn.Module] = []
        for in_dim, out_dim in itertools.pairwise(layers):
            tower.append(nn.Linear(in_dim, out_dim))
            tower.append(nn.ReLU())
            if dropout > 0:
                tower.append(nn.Dropout(dropout))
        self.mlp = nn.Sequential(*tower)
        self.out = nn.Linear(gmf_dim + layers[-1], 1)

        for embedding in (self.gmf_user, self.gmf_item, self.mlp_user, self.mlp_item):
            nn.init.normal_(embedding.weight, std=0.01)
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)

    def forward(self, users: torch.Tensor, items: torch.Tensor) -> torch.Tensor:
        gmf = self.gmf_user(users) * self.gmf_item(items)
        mlp = self.mlp(torch.cat([self.mlp_user(users), self.mlp_item(items)], dim=-1))
        return self.out(torch.cat([gmf, mlp], dim=-1)).squeeze(-1)


class NeuMF(BaseModel):
    key = "neumf"
    display_name = "NeuMF"
    supports_strong = False
    score_batch_size = 32

    def __init__(
        self,
        n_items: int,
        n_users: int = 0,
        gmf_dim: int = 8,
        mlp_dim: int = 8,
        layers: tuple[int, ...] | None = None,
        negatives: int = 4,
        lr: float = 1e-3,
        weight_decay: float = 0.0,
        dropout: float = 0.0,
        batch_size: int = 4096,
        max_epochs: int = 40,
        patience: int = 5,
        val_sample: int = 5000,
    ):
        super().__init__(n_items)
        self.n_users = int(n_users)
        self.gmf_dim = gmf_dim
        self.mlp_dim = mlp_dim
        self.layers = tuple(layers) if layers else default_layers(mlp_dim)
        self.negatives = negatives
        self.lr = lr
        self.weight_decay = weight_decay
        self.dropout = dropout
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.val_sample = val_sample
        self.net: NeuMFNet | None = None
        self.device = torch.device("cpu")

    # ------------------------------------------------------------------ train

    def _sample_negatives(self, users: np.ndarray, seen: np.ndarray, rng) -> np.ndarray:
        """Uniform negatives, rejecting anything already in the user's training row."""
        count = users.shape[0] * self.negatives
        repeated = np.repeat(users, self.negatives)
        items = rng.integers(0, self.n_items, size=count, dtype=np.int64)
        for _ in range(10):
            keys = repeated.astype(np.int64) * self.n_items + items
            collision = np.isin(keys, seen, assume_unique=False)
            if not collision.any():
                break
            items[collision] = rng.integers(0, self.n_items, size=int(collision.sum()))
        return items

    def fit(
        self,
        train,
        *,
        val_input=None,
        val_target=None,
        val_users=None,
        seed=42,
        device="cpu",
        verbose=True,
        max_epochs=None,
    ):
        torch.manual_seed(seed)
        binary = as_binary_csr(train)
        self.n_users = int(binary.shape[0])
        device = torch.device(device) if isinstance(device, str) else device
        self.device = device
        self.net = NeuMFNet(
            self.n_users, self.n_items, self.gmf_dim, self.mlp_dim, self.layers, self.dropout
        ).to(device)
        optimiser = torch.optim.Adam(
            self.net.parameters(), lr=self.lr, weight_decay=self.weight_decay
        )
        criterion = nn.BCEWithLogitsLoss()

        coo = binary.tocoo()
        pos_users = coo.row.astype(np.int64)
        pos_items = coo.col.astype(np.int64)
        seen = np.sort(pos_users * self.n_items + pos_items)

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
        best_state = None
        best_epoch = 0
        stale = 0
        started = time.perf_counter()

        for epoch in range(1, total_epochs + 1):
            rng = np.random.default_rng(seed + epoch)
            self.net.train()

            neg_items = self._sample_negatives(pos_users, seen, rng)
            neg_users = np.repeat(pos_users, self.negatives)
            users = np.concatenate([pos_users, neg_users])
            items = np.concatenate([pos_items, neg_items])
            labels = np.concatenate(
                [np.ones(pos_users.shape[0], np.float32), np.zeros(neg_users.shape[0], np.float32)]
            )
            order = rng.permutation(users.shape[0])
            users, items, labels = users[order], items[order], labels[order]

            epoch_loss = 0.0
            for start in range(0, users.shape[0], self.batch_size):
                stop = start + self.batch_size
                u = torch.from_numpy(users[start:stop]).to(device)
                i = torch.from_numpy(items[start:stop]).to(device)
                y = torch.from_numpy(labels[start:stop]).to(device)
                loss = criterion(self.net(u, i), y)
                optimiser.zero_grad(set_to_none=True)
                loss.backward()
                optimiser.step()
                epoch_loss += float(loss.detach().cpu()) * (stop - start)
            epoch_loss /= users.shape[0]

            record = {"epoch": epoch, "loss": round(epoch_loss, 5)}
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
                record["val_ndcg@20"] = metrics["ndcg@20"]
                if metrics["ndcg@20"] > best_score + 1e-6:
                    best_score = metrics["ndcg@20"]
                    best_epoch = epoch
                    best_state = {
                        k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()
                    }
                    stale = 0
                else:
                    stale += 1
            self.history.append(record)

            if verbose:
                suffix = f"  val NDCG@20={record['val_ndcg@20']:.4f}" if do_validation else ""
                print(f"    epoha {epoch:>3}/{total_epochs}  loss={epoch_loss:.5f}{suffix}")

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
        """`X_input` is ignored on purpose - NeuMF only knows user indices."""
        rows = np.asarray(rows, dtype=np.int64)
        if rows.max(initial=-1) >= self.n_users:
            raise ValueError(
                "NeuMF ne moze da skoruje korisnika koji nije bio u treningu "
                "(strong generalizacija je za ovaj model N/A)."
            )
        self.net.eval()
        out = np.empty((rows.shape[0], self.n_items), dtype=np.float32)
        items = torch.arange(self.n_items, device=self.device)
        # Every (user, item) pair goes through the MLP, so the chunk is sized by
        # a row budget rather than a user count.
        chunk = max(1, min(rows.shape[0], _ROW_BUDGET // max(1, self.n_items)))
        for start in range(0, rows.shape[0], chunk):
            block = rows[start : start + chunk]
            users = torch.from_numpy(block).to(self.device)
            user_column = torch.repeat_interleave(users, self.n_items)
            item_column = items.repeat(block.shape[0])
            logits = self.net(user_column, item_column).view(block.shape[0], self.n_items)
            out[start : start + chunk] = logits.detach().to("cpu").numpy()
        return out

    def hyperparams(self) -> dict:
        return {
            "gmf_dim": self.gmf_dim,
            "mlp_dim": self.mlp_dim,
            "mlp_layers": list(self.layers),
            "negatives_per_positive": self.negatives,
            "lr": self.lr,
            "weight_decay": self.weight_decay,
            "dropout": self.dropout,
            "batch_size": self.batch_size,
            "max_epochs": self.max_epochs,
            "patience": self.patience,
            "val_sample_users": self.val_sample,
            "pretraining": "none (simplification vs. He et al. 2017)",
            "score_user_batch": self.score_batch_size,
        }

    def _save_arrays(self, directory: Path) -> None:
        torch.save(self.net.state_dict(), directory / "model.pt")
        (directory / "n_users.txt").write_text(str(self.n_users), encoding="utf-8")

    @classmethod
    def _load_arrays(cls, directory: Path, meta: dict) -> NeuMF:
        hyper = meta.get("hyperparams", {})
        n_users = int((directory / "n_users.txt").read_text(encoding="utf-8"))
        model = cls(
            meta["n_items"],
            n_users=n_users,
            gmf_dim=hyper.get("gmf_dim", 32),
            mlp_dim=hyper.get("mlp_dim", 32),
            layers=tuple(hyper.get("mlp_layers", (64, 32, 16, 8))),
            negatives=hyper.get("negatives_per_positive", 4),
            lr=hyper.get("lr", 1e-3),
            weight_decay=hyper.get("weight_decay", 0.0),
            dropout=hyper.get("dropout", 0.0),
            batch_size=hyper.get("batch_size", 4096),
            max_epochs=hyper.get("max_epochs", 30),
            patience=hyper.get("patience", 3),
        )
        model.net = NeuMFNet(
            n_users, meta["n_items"], model.gmf_dim, model.mlp_dim, model.layers, model.dropout
        )
        state = torch.load(directory / "model.pt", map_location="cpu", weights_only=True)
        model.net.load_state_dict(state)
        model.net.eval()
        model.device = torch.device("cpu")
        return model
