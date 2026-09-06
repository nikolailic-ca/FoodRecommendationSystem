"""Popularity baseline: how many training users have a positive for this item.

The floor of the comparison table.  On a 72%-five-star dataset it is a much
stronger baseline than it looks, which is why every neural result has to be
reported next to it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from foodrec.models.base import BaseModel, as_binary_csr


class Popularity(BaseModel):
    key = "popularity"
    display_name = "Popularity"
    supports_strong = True

    def __init__(self, n_items: int) -> None:
        super().__init__(n_items)
        self.counts = np.zeros(n_items, dtype=np.float32)

    def fit(self, train, *, val_input=None, val_target=None, val_users=None,
            seed=42, device="cpu", verbose=True, max_epochs=None):
        binary = as_binary_csr(train)
        # Number of distinct training users with a positive for each item.
        self.counts = np.asarray(binary.sum(axis=0), dtype=np.float32).ravel()
        self.best_epoch = None
        if verbose:
            nonzero = int((self.counts > 0).sum())
            print(f"  popularnost izracunata: {nonzero:,} recepata sa bar jednom interakcijom")
        return self

    def score_users(self, rows, X_input):
        return np.broadcast_to(self.counts, (len(rows), self.n_items)).copy()

    def hyperparams(self) -> dict:
        return {"kind": "count of training users with a positive"}

    def _save_arrays(self, directory: Path) -> None:
        np.save(directory / "counts.npy", self.counts)

    @classmethod
    def _load_arrays(cls, directory: Path, meta: dict) -> Popularity:
        model = cls(meta["n_items"])
        model.counts = np.load(directory / "counts.npy").astype(np.float32)
        return model
