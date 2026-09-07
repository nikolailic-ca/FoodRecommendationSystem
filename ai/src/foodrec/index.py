"""The frozen id <-> matrix-index mapping.

THE bug this module exists to make impossible
---------------------------------------------
In the exploratory notebooks (ai/notebooks/03..05) the dictionaries
`user_to_idx` / `recipe_to_idx` were rebuilt with `enumerate(df[col].unique())`
several times, from different DataFrames.  `.unique()` returns ids in *order of
first appearance*, so a different row order produced a different mapping.  Model
rows were then trained under one mapping and evaluated under another, which is
why 05_ncf_v2 reported train AUC 0.83 and test AUC 0.4929 (pure chance).  On top
of that `.map()` on unseen ids yields NaN, and `.astype(np.int32)` turned those
NaN into arbitrary indices instead of raising.

The pipeline therefore builds exactly ONE mapping, from *sorted* unique ids of
the already filtered set, before any split, persists it to
ai/data/processed/index.json, and stores every split already index-encoded.  No
raw dataset id ever reaches a model, and `encode(..., strict=False)` drops
unknown ids explicitly instead of silently fabricating an index.

numpy-only on purpose: `foodrec.serving` imports this inside the FastAPI process.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class IndexMapping:
    """Immutable, order-deterministic mapping between dataset ids and matrix rows.

    `ids` is sorted and unique, so the mapping is a pure function of the *set* of
    ids - never of the row order of whatever DataFrame produced them.
    """

    __slots__ = ("ids", "to_idx")

    def __init__(self, ids: np.ndarray | list[int]) -> None:
        array = np.asarray(ids, dtype=np.int64).ravel()
        unique = np.unique(array)  # np.unique sorts; this is the whole point
        if unique.shape[0] != array.shape[0]:
            raise ValueError("IndexMapping dobija duplikate id-jeva.")
        self.ids: np.ndarray = unique
        self.ids.flags.writeable = False
        # Keys are Python ints (not np.int64) so `to_idx[int(x)]` always hits.
        self.to_idx: dict[int, int] = {int(value): i for i, value in enumerate(self.ids)}

    @classmethod
    def from_values(cls, values: np.ndarray) -> IndexMapping:
        """Build from a raw, possibly duplicated column of ids."""
        return cls(np.unique(np.asarray(values, dtype=np.int64).ravel()))

    def __len__(self) -> int:
        return int(self.ids.shape[0])

    def __contains__(self, raw_id: int) -> bool:
        return int(raw_id) in self.to_idx

    def encode(self, ids, strict: bool = False) -> np.ndarray:
        """Map raw ids to matrix indices.

        strict=False (default) drops unknown ids; strict=True raises.  There is
        no third option that silently invents an index.
        """
        array = np.asarray(ids, dtype=np.int64).ravel()
        if array.size == 0:
            return np.empty(0, dtype=np.int64)
        lookup = np.searchsorted(self.ids, array)
        np.clip(lookup, 0, len(self) - 1, out=lookup)
        known = self.ids[lookup] == array
        if not known.all():
            if strict:
                missing = array[~known][:5].tolist()
                raise KeyError(f"Nepoznati id-jevi u encode(): {missing}")
            lookup = lookup[known]
        return lookup.astype(np.int64, copy=False)

    def encode_mask(self, ids) -> tuple[np.ndarray, np.ndarray]:
        """Like `encode`, but also returns the boolean keep-mask (aligned to input)."""
        array = np.asarray(ids, dtype=np.int64).ravel()
        if array.size == 0:
            return np.empty(0, dtype=np.int64), np.zeros(0, dtype=bool)
        lookup = np.searchsorted(self.ids, array)
        np.clip(lookup, 0, len(self) - 1, out=lookup)
        known = self.ids[lookup] == array
        return lookup[known].astype(np.int64, copy=False), known

    def decode(self, indices) -> np.ndarray:
        """Map matrix indices back to raw dataset ids."""
        array = np.asarray(indices, dtype=np.int64).ravel()
        if array.size and (array.min() < 0 or array.max() >= len(self)):
            raise IndexError("decode() je dobio indeks van opsega.")
        return self.ids[array]

    def to_dict(self) -> dict:
        return {"n": len(self), "ids": self.ids.tolist()}

    @classmethod
    def from_dict(cls, payload: dict) -> IndexMapping:
        return cls(np.asarray(payload["ids"], dtype=np.int64))

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> IndexMapping:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save_index_pair(path: Path, users: IndexMapping, items: IndexMapping) -> None:
    """Persist both mappings into a single ai/data/processed/index.json."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "n_users": len(users),
        "n_items": len(items),
        "user_ids": users.ids.tolist(),
        "item_ids": items.ids.tolist(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def load_index_pair(path: Path) -> tuple[IndexMapping, IndexMapping]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return (
        IndexMapping(np.asarray(payload["user_ids"], dtype=np.int64)),
        IndexMapping(np.asarray(payload["item_ids"], dtype=np.int64)),
    )
