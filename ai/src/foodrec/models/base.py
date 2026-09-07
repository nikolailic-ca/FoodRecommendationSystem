"""Common contract for every model in the thesis comparison.

A model is trained once on `train` and must be able to score users in both
evaluation views.  The single scoring entry point is

    score_users(rows, X_input) -> ndarray (len(rows), n_items)

where `rows` are user indices in the frozen mapping and `X_input` is the CSR
matrix that supplies the user's known history for that view (training positives
in the weak view, the fold-in matrix in the strong view).

Item-based models ignore `rows` and read `X_input[rows]`: that is precisely what
lets them serve users who were never in training.  NeuMF ignores `X_input` and
indexes an embedding table by `rows`, which is why `supports_strong = False`.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from scipy.sparse import csr_array


class BaseModel(ABC):
    key: str = "base"
    display_name: str = "Base"
    #: can the model score a user it never saw during training?
    supports_strong: bool = True
    #: user-batch size used by the evaluator (NeuMF needs a small one)
    score_batch_size: int = 500

    def __init__(self, n_items: int) -> None:
        self.n_items = int(n_items)
        self.best_epoch: int | None = None
        self.train_time_s: float = 0.0
        self.history: list[dict] = []

    # ------------------------------------------------------------------ train

    @abstractmethod
    def fit(
        self,
        train: csr_array,
        *,
        val_input: csr_array | None = None,
        val_target: csr_array | None = None,
        val_users: np.ndarray | None = None,
        seed: int = 42,
        device: str = "cpu",
        verbose: bool = True,
        max_epochs: int | None = None,
    ) -> BaseModel:
        """Fit on the binary training matrix.  `max_epochs` overrides early stopping."""

    # ------------------------------------------------------------------ score

    @abstractmethod
    def score_users(self, rows: np.ndarray, X_input: csr_array) -> np.ndarray:
        """Dense scores over the whole catalog for the given users."""

    def scorer(self, X_input: csr_array):
        """Adapter for foodrec.metrics.evaluate_ranking."""

        def score_fn(rows: np.ndarray) -> np.ndarray:
            return self.score_users(rows, X_input)

        return score_fn

    # ------------------------------------------------------------- persistence

    def hyperparams(self) -> dict:
        return {}

    @abstractmethod
    def _save_arrays(self, directory: Path) -> None: ...

    @classmethod
    @abstractmethod
    def _load_arrays(cls, directory: Path, meta: dict) -> BaseModel: ...

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self._save_arrays(directory)
        meta = {
            "key": self.key,
            "display_name": self.display_name,
            "n_items": self.n_items,
            "best_epoch": self.best_epoch,
            "train_time_s": round(self.train_time_s, 2),
            "supports_strong": self.supports_strong,
            "hyperparams": self.hyperparams(),
            "history": self.history,
        }
        (directory / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, directory: Path) -> BaseModel:
        directory = Path(directory)
        meta_path = directory / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(
                f"Model nije istreniran: nema {meta_path}. "
                f"Pokrenite: uv run python -m foodrec.train --model {cls.key}"
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        model = cls._load_arrays(directory, meta)
        model.best_epoch = meta.get("best_epoch")
        model.train_time_s = meta.get("train_time_s", 0.0)
        model.history = meta.get("history", [])
        return model


def as_binary_csr(matrix: csr_array) -> csr_array:
    """Defensive copy with all stored values set to 1.0 (float32)."""
    out = csr_array(matrix, dtype=np.float32, copy=True)
    out.data[:] = 1.0
    return out


def iter_gram_blocks(binary: csr_array, block: int = 4096):
    """Yield `(start, stop, G)` where G = X.T @ X restricted to columns [start, stop).

    A naive `X.T @ X` on Food.com allocates one sparse intermediate for the whole
    42k x 42k co-occurrence matrix; heavy users (thousands of positives) make it
    nearly dense and the process dies.  Working in column blocks caps the
    intermediate at n_items x block and lets the caller write straight into a
    preallocated dense buffer.
    """
    from scipy.sparse import csc_array

    n_items = int(binary.shape[1])
    transposed = csr_array(binary.T)  # (n_items, n_users)
    by_column = csc_array(binary)
    for start in range(0, n_items, block):
        stop = min(start + block, n_items)
        gram = (transposed @ by_column[:, start:stop]).toarray().astype(np.float32, copy=False)
        yield start, stop, gram
