"""Item-based k-nearest-neighbour collaborative filtering.

Similarity is cosine with shrinkage:

    s_ij = c_ij / (sqrt(n_i * n_j) + shrink)

where c_ij is the number of users with a positive for both items and n_i is the
item's popularity.  The shrinkage term (10) is what keeps two obscure recipes
that were co-rated exactly once from scoring a perfect 1.0 - without it the
neighbourhood fills up with noise and Recall collapses.

Only the top k=100 neighbours per item are kept, so S stays sparse and scoring
is a single sparse product: scores = history @ S.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.sparse import csr_array

from foodrec.models.base import BaseModel, as_binary_csr, iter_gram_blocks


class ItemKNN(BaseModel):
    key = "itemknn"
    display_name = "ItemKNN"
    supports_strong = True

    def __init__(self, n_items: int, k: int = 100, shrinkage: float = 10.0, block: int = 4096):
        super().__init__(n_items)
        self.k = int(k)
        self.shrinkage = float(shrinkage)
        self.block = int(block)
        self.similarity: csr_array | None = None

    def fit(self, train, *, val_input=None, val_target=None, val_users=None,
            seed=42, device="cpu", verbose=True, max_epochs=None):
        binary = as_binary_csr(train)
        n_items = self.n_items
        popularity = np.asarray(binary.sum(axis=0), dtype=np.float32).ravel()
        norm = np.sqrt(popularity, dtype=np.float32)

        keep = min(self.k, n_items - 1)
        rows: list[np.ndarray] = []
        cols: list[np.ndarray] = []
        values: list[np.ndarray] = []

        for start, stop, gram in iter_gram_blocks(binary, self.block):
            width = stop - start
            # One temporary, not three: at 42k items each (n_items, block)
            # float32 buffer is ~700 MB.
            denominator = np.multiply(norm[:, None], norm[None, start:stop])
            denominator += self.shrinkage
            gram /= denominator
            del denominator
            # An item is not its own neighbour.
            gram[np.arange(start, stop), np.arange(width)] = 0.0

            top = np.argpartition(-gram, kth=keep - 1, axis=0)[:keep]  # (keep, width)
            top_values = np.take_along_axis(gram, top, axis=0)
            mask = top_values > 0
            column_index = np.broadcast_to(np.arange(start, stop), top.shape)
            rows.append(top[mask])
            cols.append(column_index[mask])
            values.append(top_values[mask])
            if verbose:
                print(f"    blok kolona {start:>7,}-{stop:>7,}", end="\r")

        row_index = np.concatenate(rows) if rows else np.empty(0, dtype=np.int64)
        col_index = np.concatenate(cols) if cols else np.empty(0, dtype=np.int64)
        data = np.concatenate(values).astype(np.float32) if values else np.empty(0, np.float32)
        self.similarity = csr_array(
            (data, (row_index, col_index)), shape=(n_items, n_items), dtype=np.float32
        )
        self.best_epoch = None
        if verbose:
            print(f"    matrica slicnosti: {self.similarity.nnz:,} nenultih elemenata      ")
        return self

    def score_users(self, rows, X_input):
        history = csr_array(X_input)[np.asarray(rows, dtype=np.int64)]
        scores = history @ self.similarity
        return np.asarray(scores.todense() if hasattr(scores, "todense") else scores, np.float32)

    def hyperparams(self) -> dict:
        return {"k": self.k, "shrinkage": self.shrinkage, "gram_block": self.block,
                "similarity": "cosine with shrinkage"}

    def _save_arrays(self, directory: Path) -> None:
        np.savez_compressed(
            directory / "similarity.npz",
            data=self.similarity.data,
            indices=self.similarity.indices,
            indptr=self.similarity.indptr,
            shape=np.asarray(self.similarity.shape, dtype=np.int64),
        )

    @classmethod
    def _load_arrays(cls, directory: Path, meta: dict) -> ItemKNN:
        hyper = meta.get("hyperparams", {})
        model = cls(
            meta["n_items"],
            k=hyper.get("k", 100),
            shrinkage=hyper.get("shrinkage", 10.0),
            block=hyper.get("gram_block", 4096),
        )
        with np.load(directory / "similarity.npz") as payload:
            model.similarity = csr_array(
                (payload["data"], payload["indices"], payload["indptr"]),
                shape=tuple(int(v) for v in payload["shape"]),
            )
        return model
