"""EASE - Embarrassingly Shallow Autoencoder (Steck, WWW 2019).

Closed-form item-item model:

    G = X.T X + lambda I
    P = G^-1
    B = -P / diag(P),   diag(B) := 0
    scores = X B

No gradient descent at all, and on dense-ish implicit data it is usually within
a point or two of Mult-VAE - which is exactly why it belongs in the thesis
comparison next to the neural models.

lambda defaults to 5000, not the textbook 500.  Two things force that here.  G is
39,886 x 39,886 but has rank at most n_users = 25,959, so it is singular and lambda
cannot be small: at lambda=1 validation Recall@20 collapses to 0.0173.  And the
median recipe has five training interactions, so a diagonal of ~8 needs heavy
damping before the regression stops chasing noise.  The validation sweep rises
monotonically (0.0173 at 1, 0.0310 at 50, 0.0354 at 500, 0.0373 at 2000) and
plateaus at 5000, which is the argmax by NDCG@20.

Memory: B is a dense n_items x n_items float32 matrix.  For the ~42k Food.com
items that is 7 GB, with a peak near 9 GB during the inversion, so this model is
trained in its own process and never alongside an MPS job.  The Gram matrix is
accumulated in column blocks straight into the preallocated buffer, which avoids
a second full-size sparse intermediate.  `--max-items` restricts the model to the
most popular head of the catalog as a documented fallback for smaller machines.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.sparse import csr_array

from foodrec.models.base import BaseModel, as_binary_csr, iter_gram_blocks


class EASE(BaseModel):
    key = "ease"
    display_name = "EASE"
    supports_strong = True

    def __init__(self, n_items: int, reg: float = 5000.0, max_items: int | None = None,
                 block: int = 4096):
        super().__init__(n_items)
        self.reg = float(reg)
        self.max_items = max_items
        self.block = int(block)
        self.weights: np.ndarray | None = None  # (m, m) float32, m = len(selected)
        self.selected: np.ndarray | None = None  # None means "the whole catalog"

    def fit(self, train, *, val_input=None, val_target=None, val_users=None,
            seed=42, device="cpu", verbose=True, max_epochs=None):
        binary = as_binary_csr(train)

        if self.max_items is not None and self.max_items < self.n_items:
            popularity = np.asarray(binary.sum(axis=0)).ravel()
            self.selected = np.sort(np.argsort(-popularity, kind="stable")[: self.max_items])
            binary = csr_array(binary[:, self.selected])
            if verbose:
                print(f"    OGRANICENJE: EASE koristi {self.max_items:,} najpopularnijih recepata")
        else:
            self.selected = None

        m = int(binary.shape[1])
        if verbose:
            print(f"    Gram matrica {m:,} x {m:,} float32 ({m * m * 4 / 2**30:.2f} GB)")

        # Fortran order matters: scipy.linalg.inv only honours overwrite_a on a
        # column-major buffer, otherwise it copies and the peak doubles to 14 GB.
        # G is symmetric, so column-major also makes the block writes contiguous.
        gram = np.zeros((m, m), dtype=np.float32, order='F')
        for start, stop, block_values in iter_gram_blocks(binary, self.block):
            gram[:, start:stop] = block_values
            if verbose:
                print(f"    blok kolona {start:>7,}-{stop:>7,}", end="\r")

        diagonal = np.arange(m)
        gram[diagonal, diagonal] += self.reg

        from scipy.linalg import inv

        if verbose:
            print("    inverzija (in-place)...                    ")
        precision = inv(gram, overwrite_a=True, check_finite=False)
        del gram

        # B_ij = -P_ij / P_jj  (column-wise division), zero diagonal.
        precision /= -np.diag(precision)[None, :]
        precision[diagonal, diagonal] = 0.0
        self.weights = precision
        self.best_epoch = None
        if verbose:
            print(f"    B: {m:,} x {m:,}, srednja |vrednost| = {np.abs(self.weights).mean():.5f}")
        return self

    def score_users(self, rows, X_input):
        rows = np.asarray(rows, dtype=np.int64)
        history = csr_array(X_input)[rows]
        if self.selected is None:
            return np.asarray(history @ self.weights, dtype=np.float32)

        scores = np.full((rows.shape[0], self.n_items), -np.inf, dtype=np.float32)
        scores[:, self.selected] = np.asarray(
            csr_array(history[:, self.selected]) @ self.weights, dtype=np.float32
        )
        return scores

    def hyperparams(self) -> dict:
        return {
            "lambda": self.reg,
            "max_items": self.max_items,
            "gram_block": self.block,
            "storage_dtype": "float16",
        }

    def _save_arrays(self, directory: Path) -> None:
        # float16 on disk: B entries are O(1e-3..1e-1) and scores are sums of a
        # few dozen of them, so the rounding never changes the ranking, while a
        # 42k-item model drops from 7 GB to 3.5 GB.
        np.save(directory / "weights.npy", self.weights.astype(np.float16))
        if self.selected is not None:
            np.save(directory / "selected.npy", self.selected)

    @classmethod
    def _load_arrays(cls, directory: Path, meta: dict) -> EASE:
        hyper = meta.get("hyperparams", {})
        model = cls(meta["n_items"], reg=hyper.get("lambda", 500.0),
                    max_items=hyper.get("max_items"), block=hyper.get("gram_block", 4096))
        model.weights = np.load(directory / "weights.npy").astype(np.float32)
        selected_path = directory / "selected.npy"
        model.selected = np.load(selected_path) if selected_path.exists() else None
        return model
