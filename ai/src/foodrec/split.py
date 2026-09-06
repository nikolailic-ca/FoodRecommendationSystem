"""One split, two evaluation views.

Every model is trained exactly once, on `train`, and evaluated in both views:

  weak generalization   (primary)
      users:  the 90% of users that are in training
      input:  their 70% training positives
      target: their 20% test positives
      masked: train + validation items (validation items are held out from
              training, so counting them as mistakes would only add noise)

  strong generalization (secondary, cold-start argument of the thesis)
      users:  the 10% of users held out entirely - no row of theirs is in `train`
      input:  80% of their positives, folded in at inference time
      target: the remaining 20%
      NeuMF cannot do this at all (it has no embedding row for an unseen user),
      which is exactly the point we report.

All five matrices are (n_users, n_items) with empty rows where a view does not
apply, so one matrix layout serves every model and no re-indexing ever happens.
Indices are the frozen ones from ai/data/processed/index.json - see foodrec.index.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_array

from foodrec import config
from foodrec.data import load_positives

VIEW_MATRICES = ("train", "weak_val", "weak_test", "strong_input", "strong_target")


def splits_path(seed: int = config.SEED) -> Path:
    return config.PROCESSED_DIR / f"splits_seed{seed}.npz"


class Splits:
    """Container for the five CSR views plus the user partition."""

    __slots__ = (
        "meta",
        "seed",
        "strong_input",
        "strong_target",
        "strong_users",
        "train",
        "weak_test",
        "weak_users",
        "weak_val",
    )

    def __init__(
        self,
        train: csr_array,
        weak_val: csr_array,
        weak_test: csr_array,
        strong_input: csr_array,
        strong_target: csr_array,
        weak_users: np.ndarray,
        strong_users: np.ndarray,
        seed: int,
        meta: dict | None = None,
    ) -> None:
        self.train = train
        self.weak_val = weak_val
        self.weak_test = weak_test
        self.strong_input = strong_input
        self.strong_target = strong_target
        self.weak_users = weak_users
        self.strong_users = strong_users
        self.seed = seed
        self.meta = meta or {}

    @property
    def n_users(self) -> int:
        return int(self.train.shape[0])

    @property
    def n_items(self) -> int:
        return int(self.train.shape[1])

    @property
    def weak_mask(self) -> csr_array:
        """Items excluded from ranking in the weak test view: train + validation."""
        combined = (self.train + self.weak_val).tocsr()
        combined.data[:] = 1.0
        return csr_array(combined)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, np.ndarray] = {
            "shape": np.asarray([self.n_users, self.n_items], dtype=np.int64),
            "seed": np.asarray([self.seed], dtype=np.int64),
            "weak_users": self.weak_users.astype(np.int32, copy=False),
            "strong_users": self.strong_users.astype(np.int32, copy=False),
        }
        for name in VIEW_MATRICES:
            matrix = getattr(self, name)
            payload[f"{name}_indptr"] = matrix.indptr.astype(np.int64, copy=False)
            payload[f"{name}_indices"] = matrix.indices.astype(np.int32, copy=False)
        np.savez_compressed(path, **payload)
        path.with_suffix(".meta.json").write_text(json.dumps(self.meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Splits:
        path = Path(path)
        if not path.exists():
            raise SystemExit(
                "GRESKA: podela ne postoji.\n"
                f"Ocekivano: {path}\n"
                "Pokrenite prvo: uv run python -m foodrec.split --seed 42"
            )
        with np.load(path) as payload:
            shape = tuple(int(value) for value in payload["shape"])
            seed = int(payload["seed"][0])
            matrices = {}
            for name in VIEW_MATRICES:
                indptr = payload[f"{name}_indptr"].astype(np.int64)
                indices = payload[f"{name}_indices"].astype(np.int32)
                data = np.ones(indices.shape[0], dtype=np.float32)
                matrices[name] = csr_array((data, indices, indptr), shape=shape)
            weak_users = payload["weak_users"].astype(np.int64)
            strong_users = payload["strong_users"].astype(np.int64)
        meta_path = path.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        return cls(seed=seed, weak_users=weak_users, strong_users=strong_users, meta=meta, **matrices)


def _split_counts(n: int, test_fraction: float, val_fraction: float) -> tuple[int, int, int]:
    """Per-user holdout sizes; the user always keeps at least one training item."""
    n_test = max(1, int(test_fraction * n + 0.5))
    n_val = max(1, int(val_fraction * n + 0.5))
    while n - n_test - n_val < 1:
        if n_val > 0:
            n_val -= 1
        elif n_test > 1:
            n_test -= 1
        else:  # pragma: no cover - k-core guarantees n >= 3
            break
    return n - n_test - n_val, n_val, n_test


def build_splits(seed: int = config.SEED) -> Splits:
    data = load_positives()
    n_users, n_items = data.n_users, data.n_items

    full = data.matrix().tocsr()
    full.data[:] = 1.0
    indptr, indices = full.indptr, full.indices

    rng = np.random.default_rng(seed)
    permutation = rng.permutation(n_users)
    n_strong = max(1, int(config.STRONG_USER_FRACTION * n_users + 0.5))
    strong_users = np.sort(permutation[:n_strong]).astype(np.int64)
    weak_users = np.sort(permutation[n_strong:]).astype(np.int64)
    is_strong = np.zeros(n_users, dtype=bool)
    is_strong[strong_users] = True

    buckets: dict[str, tuple[list[np.ndarray], list[np.ndarray]]] = {
        name: ([], []) for name in VIEW_MATRICES
    }

    def add(name: str, user: int, items: np.ndarray) -> None:
        if items.size == 0:
            return
        rows, cols = buckets[name]
        rows.append(np.full(items.shape[0], user, dtype=np.int32))
        cols.append(items.astype(np.int32, copy=False))

    # Users are visited in index order, so the split is a pure function of the seed.
    for user in range(n_users):
        items = indices[indptr[user] : indptr[user + 1]]
        shuffled = items[rng.permutation(items.shape[0])]
        n = shuffled.shape[0]
        if is_strong[user]:
            n_in = max(1, int(config.STRONG_FOLD_IN_FRACTION * n + 0.5))
            n_in = min(n_in, n - 1) if n > 1 else n
            add("strong_input", user, shuffled[:n_in])
            add("strong_target", user, shuffled[n_in:])
        else:
            n_train, n_val, _ = _split_counts(n, config.TEST_FRACTION, config.VAL_FRACTION)
            add("train", user, shuffled[:n_train])
            add("weak_val", user, shuffled[n_train : n_train + n_val])
            add("weak_test", user, shuffled[n_train + n_val :])

    matrices = {}
    for name, (rows, cols) in buckets.items():
        if rows:
            row_index = np.concatenate(rows)
            col_index = np.concatenate(cols)
        else:  # pragma: no cover - never empty in practice
            row_index = np.empty(0, dtype=np.int32)
            col_index = np.empty(0, dtype=np.int32)
        matrices[name] = csr_array(
            (np.ones(row_index.shape[0], dtype=np.float32), (row_index, col_index)),
            shape=(n_users, n_items),
        )

    meta = {
        "seed": seed,
        "n_users": n_users,
        "n_items": n_items,
        "n_weak_users": int(weak_users.shape[0]),
        "n_strong_users": int(strong_users.shape[0]),
        "test_fraction": config.TEST_FRACTION,
        "val_fraction": config.VAL_FRACTION,
        "strong_user_fraction": config.STRONG_USER_FRACTION,
        "strong_fold_in_fraction": config.STRONG_FOLD_IN_FRACTION,
        "nnz": {name: int(matrix.nnz) for name, matrix in matrices.items()},
        "dataset_stats": data.stats,
    }
    return Splits(
        seed=seed, weak_users=weak_users, strong_users=strong_users, meta=meta, **matrices
    )


def check_splits(splits: Splits, verbose: bool = True) -> dict:
    """Assert the invariants that the notebooks silently broke."""
    n_users, n_items = splits.n_users, splits.n_items

    for name in VIEW_MATRICES:
        matrix = getattr(splits, name)
        assert matrix.shape == (n_users, n_items), f"{name} ima pogresan oblik {matrix.shape}"
        if matrix.nnz:
            assert matrix.indices.min() >= 0 and matrix.indices.max() < n_items, (
                f"{name}: indeks recepta van opsega"
            )

    # A user's positives may live in exactly one bucket per view.
    weak_sum = splits.train + splits.weak_val + splits.weak_test
    assert weak_sum.nnz == splits.train.nnz + splits.weak_val.nnz + splits.weak_test.nnz, (
        "weak view: train/val/test se preklapaju"
    )
    assert weak_sum.data.max() <= 1.0, "weak view: duplirana interakcija"

    strong_sum = splits.strong_input + splits.strong_target
    assert strong_sum.nnz == splits.strong_input.nnz + splits.strong_target.nnz, (
        "strong view: fold-in i target se preklapaju"
    )

    # The user partition must be a true partition.
    assert splits.weak_users.shape[0] + splits.strong_users.shape[0] == n_users
    assert np.intersect1d(splits.weak_users, splits.strong_users).size == 0

    # Strong users must be invisible during training.
    train_rows = np.diff(splits.train.indptr)
    assert train_rows[splits.strong_users].sum() == 0, "strong korisnici curenje u train"
    assert train_rows[splits.weak_users].min() >= 1, "weak korisnik bez trening stavke"

    weak_test_rows = np.diff(splits.weak_test.indptr)
    strong_target_rows = np.diff(splits.strong_target.indptr)
    assert weak_test_rows[splits.weak_users].min() >= 1, "weak korisnik bez test stavke"
    assert strong_target_rows[splits.strong_users].min() >= 1, "strong korisnik bez targeta"
    assert weak_test_rows[splits.strong_users].sum() == 0
    assert strong_target_rows[splits.weak_users].sum() == 0

    items_in_train = np.unique(splits.train.indices).shape[0] if splits.train.nnz else 0
    cold_items = n_items - items_in_train
    report = {
        "n_users": n_users,
        "n_items": n_items,
        "n_weak_users": int(splits.weak_users.shape[0]),
        "n_strong_users": int(splits.strong_users.shape[0]),
        "nnz": {name: int(getattr(splits, name).nnz) for name in VIEW_MATRICES},
        "items_without_training_interaction": int(cold_items),
        "items_without_training_interaction_pct": round(100.0 * cold_items / n_items, 4),
        "median_train_per_weak_user": float(np.median(train_rows[splits.weak_users])),
    }
    if verbose:
        print("  provere podele: OK (disjunktnost, opseg indeksa, particija korisnika)")
        print(
            f"  recepti bez ijedne trening interakcije: {cold_items:,} "
            f"({report['items_without_training_interaction_pct']}%)"
        )
        if report["items_without_training_interaction_pct"] > 1.0:
            print("  UPOZORENJE: preko 1% recepata nema trening interakciju.")
    return report


def load_splits(seed: int = config.SEED) -> Splits:
    return Splits.load(splits_path(seed))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m foodrec.split",
        description="Jedna podela, dva pogleda evaluacije (weak i strong generalizacija).",
    )
    parser.add_argument("--seed", type=int, default=config.SEED)
    args = parser.parse_args(argv)

    config.ensure_dirs()
    splits = build_splits(args.seed)
    report = check_splits(splits)
    splits.meta["check"] = report
    path = splits_path(args.seed)
    splits.save(path)

    print("=" * 68)
    print(f"PODELA PODATAKA (seed={args.seed})")
    print("=" * 68)
    print(f"  korisnici: {splits.n_users:,}  recepti: {splits.n_items:,}")
    print(
        f"  weak korisnici  : {report['n_weak_users']:,} "
        f"(train {report['nnz']['train']:,} / val {report['nnz']['weak_val']:,} "
        f"/ test {report['nnz']['weak_test']:,})"
    )
    print(
        f"  strong korisnici: {report['n_strong_users']:,} "
        f"(fold-in {report['nnz']['strong_input']:,} / target {report['nnz']['strong_target']:,})"
    )
    print(f"  medijana trening stavki po korisniku: {report['median_train_per_weak_user']:.0f}")
    print(f"  sacuvano -> {path}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
