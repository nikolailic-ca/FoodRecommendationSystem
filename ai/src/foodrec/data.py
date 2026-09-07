"""Raw Food.com CSVs -> filtered implicit-feedback matrix with a frozen index.

Pipeline (in this exact order, and the order matters):

  1. read only the needed columns, cast ids to int64
  2. keep interactions whose recipe exists in RAW_recipes.csv (the served catalog)
  3. drop duplicate (user, recipe) pairs, keeping the maximum rating
  4. positives = rating >= 4          (rating 0 means "review without a rating")
  5. iterative k-core: users >= 3 positives, items >= 5 positives, to convergence
  6. ONLY THEN build the frozen IndexMapping from the sorted unique ids
  7. persist index.json + stats.json + positives.npz (already index-encoded)

Steps 5 and 6 must not be swapped: the mapping has to describe the final set, so
that indices are dense, contiguous and stable across every later run.

pandas 3 notes: copy-on-write is the default (no chained-assignment writes here)
and the new string dtype is irrelevant because we only ever read integer columns.
Parquet is deliberately avoided - pyarrow is not installed on the target machine.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from foodrec import config
from foodrec.index import IndexMapping, load_index_pair, save_index_pair

__all__ = ["IndexMapping", "PositiveData", "build_dataset", "load_positives"]


class PositiveData:
    """Everything downstream needs: encoded positives plus the frozen mappings."""

    __slots__ = ("item_idx", "items", "stats", "user_idx", "users")

    def __init__(
        self,
        user_idx: np.ndarray,
        item_idx: np.ndarray,
        users: IndexMapping,
        items: IndexMapping,
        stats: dict,
    ) -> None:
        self.user_idx = user_idx
        self.item_idx = item_idx
        self.users = users
        self.items = items
        self.stats = stats

    @property
    def n_users(self) -> int:
        return len(self.users)

    @property
    def n_items(self) -> int:
        return len(self.items)

    def matrix(self):
        """Full binary user-item matrix (all positives, no split)."""
        from scipy.sparse import csr_array

        data = np.ones(self.user_idx.shape[0], dtype=np.float32)
        return csr_array(
            (data, (self.user_idx, self.item_idx)),
            shape=(self.n_users, self.n_items),
        )


# --------------------------------------------------------------------- reading


def _require_dataset(datasets_dir: Path) -> tuple[Path, Path]:
    recipes = datasets_dir / "RAW_recipes.csv"
    interactions = datasets_dir / "RAW_interactions.csv"
    if not recipes.exists() or not interactions.exists():
        print(config.dataset_missing_message(datasets_dir), file=sys.stderr)
        raise SystemExit(1)
    return recipes, interactions


def _read_raw(datasets_dir: Path) -> tuple[object, np.ndarray]:
    import pandas as pd

    recipes_path, interactions_path = _require_dataset(datasets_dir)

    # Only `id` is needed from the recipe file: it defines the served catalog.
    recipes = pd.read_csv(recipes_path, usecols=["id"], dtype={"id": "int64"})
    catalog_ids = np.unique(recipes["id"].to_numpy(dtype=np.int64))

    interactions = pd.read_csv(
        interactions_path,
        usecols=["user_id", "recipe_id", "rating"],
        dtype={"user_id": "int64", "recipe_id": "int64", "rating": "float64"},
    )
    return interactions, catalog_ids


# ------------------------------------------------------------------- filtering


def _iterative_kcore(
    user_ids: np.ndarray,
    item_ids: np.ndarray,
    min_user: int,
    min_item: int,
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Alternate user/item pruning until nothing else drops out."""
    history: list[dict] = []
    for iteration in range(1, 101):
        unique_users, user_counts = np.unique(user_ids, return_counts=True)
        thin_users = unique_users[user_counts < min_user]
        unique_items, item_counts = np.unique(item_ids, return_counts=True)
        thin_items = unique_items[item_counts < min_item]

        history.append(
            {
                "iteration": iteration,
                "interactions": int(user_ids.shape[0]),
                "users": int(unique_users.shape[0]),
                "items": int(unique_items.shape[0]),
                "dropped_users": int(thin_users.shape[0]),
                "dropped_items": int(thin_items.shape[0]),
            }
        )
        if thin_users.size == 0 and thin_items.size == 0:
            break

        keep = np.ones(user_ids.shape[0], dtype=bool)
        if thin_users.size:
            keep &= ~np.isin(user_ids, thin_users)
        if thin_items.size:
            keep &= ~np.isin(item_ids, thin_items)
        user_ids = user_ids[keep]
        item_ids = item_ids[keep]
        if user_ids.size == 0:
            raise SystemExit(
                "GRESKA: k-core je uklonio sve interakcije. Proverite prag pozitivne ocene."
            )
    return user_ids, item_ids, history


# ---------------------------------------------------------------------- build


def build_dataset(datasets_dir: Path | None = None, verbose: bool = True) -> PositiveData:
    """Run the whole filtering chain and persist index.json / stats.json / positives.npz."""
    datasets_dir = Path(datasets_dir) if datasets_dir is not None else config.DATASETS_DIR
    started = time.perf_counter()

    interactions, catalog_ids = _read_raw(datasets_dir)
    n_raw = int(interactions.shape[0])

    ratings = interactions["rating"].to_numpy(dtype=np.float64)
    n_zero_rating = int((ratings == 0).sum())
    rating_histogram = {
        str(int(value)): int(count)
        for value, count in zip(*np.unique(ratings, return_counts=True), strict=True)
    }

    # 2) restrict to recipes that actually exist in the catalog
    in_catalog = np.isin(interactions["recipe_id"].to_numpy(dtype=np.int64), catalog_ids)
    interactions = interactions[in_catalog]
    n_in_catalog = int(interactions.shape[0])

    # 3) duplicate (user, recipe) -> keep the maximum rating
    interactions = interactions.groupby(["user_id", "recipe_id"], as_index=False, sort=False)[
        "rating"
    ].max()
    n_dedup = int(interactions.shape[0])

    # 4) implicit positives
    positives = interactions[interactions["rating"] >= config.POSITIVE_THRESHOLD]
    user_ids = positives["user_id"].to_numpy(dtype=np.int64)
    item_ids = positives["recipe_id"].to_numpy(dtype=np.int64)
    n_positives = int(user_ids.shape[0])
    users_before = int(np.unique(user_ids).shape[0])
    items_before = int(np.unique(item_ids).shape[0])

    # 5) iterative k-core
    user_ids, item_ids, kcore_history = _iterative_kcore(
        user_ids, item_ids, config.MIN_USER_POSITIVES, config.MIN_ITEM_POSITIVES
    )

    # 6) the single frozen mapping, from the sorted unique ids of the final set
    users = IndexMapping.from_values(user_ids)
    items = IndexMapping.from_values(item_ids)
    user_idx = users.encode(user_ids, strict=True).astype(np.int32, copy=False)
    item_idx = items.encode(item_ids, strict=True).astype(np.int32, copy=False)

    _, per_user = np.unique(user_idx, return_counts=True)
    _, per_item = np.unique(item_idx, return_counts=True)

    stats = {
        "datasets_dir": str(datasets_dir),
        "n_interactions_raw": n_raw,
        "n_interactions_in_catalog": n_in_catalog,
        "n_interactions_dedup": n_dedup,
        "n_catalog_recipes": int(catalog_ids.shape[0]),
        "n_rating_zero": n_zero_rating,
        "rating_histogram": rating_histogram,
        "positive_threshold": config.POSITIVE_THRESHOLD,
        "n_positives_before_kcore": n_positives,
        "n_users_before_kcore": users_before,
        "n_items_before_kcore": items_before,
        "kcore": {
            "min_user_positives": config.MIN_USER_POSITIVES,
            "min_item_positives": config.MIN_ITEM_POSITIVES,
            "iterations": len(kcore_history),
            "history": kcore_history,
        },
        "n_positives": int(user_idx.shape[0]),
        "n_users": len(users),
        "n_items": len(items),
        "density": float(user_idx.shape[0] / (len(users) * len(items))),
        "min_user_positives_final": int(per_user.min()),
        "max_user_positives_final": int(per_user.max()),
        "mean_user_positives_final": float(per_user.mean()),
        "min_item_positives_final": int(per_item.min()),
        "max_item_positives_final": int(per_item.max()),
        "mean_item_positives_final": float(per_item.mean()),
        "build_seconds": round(time.perf_counter() - started, 2),
    }

    config.ensure_dirs()
    save_index_pair(config.INDEX_JSON, users, items)
    config.STATS_JSON.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    np.savez_compressed(config.POSITIVES_NPZ, user_idx=user_idx, item_idx=item_idx)

    if verbose:
        _print_report(stats)
    return PositiveData(user_idx, item_idx, users, items, stats)


def _print_report(stats: dict) -> None:
    print("=" * 68)
    print("PRIPREMA PODATAKA (foodrec.data)")
    print("=" * 68)
    print(f"  sirove interakcije                : {stats['n_interactions_raw']:>10,}")
    print(f"  ocena 0 (recenzija bez ocene)     : {stats['n_rating_zero']:>10,}")
    print(f"  recepti u katalogu                : {stats['n_catalog_recipes']:>10,}")
    print(f"  posle filtera po katalogu         : {stats['n_interactions_in_catalog']:>10,}")
    print(f"  posle dedup (user, recipe)        : {stats['n_interactions_dedup']:>10,}")
    print(
        f"  pozitivne (rating >= {stats['positive_threshold']})          : "
        f"{stats['n_positives_before_kcore']:>10,}"
        f"   ({stats['n_users_before_kcore']:,} korisnika, {stats['n_items_before_kcore']:,} recepata)"
    )
    print("-" * 68)
    kcore = stats["kcore"]
    print(
        f"  k-core (user>={kcore['min_user_positives']}, item>={kcore['min_item_positives']}), "
        f"{kcore['iterations']} iteracija:"
    )
    for step in kcore["history"]:
        print(
            f"    #{step['iteration']:<2} interakcije={step['interactions']:>9,}  "
            f"korisnici={step['users']:>7,}  recepti={step['items']:>7,}  "
            f"izbaceno: {step['dropped_users']:,} kor. / {step['dropped_items']:,} rec."
        )
    print("-" * 68)
    print(f"  finalno: {stats['n_positives']:,} pozitivnih interakcija")
    print(f"           {stats['n_users']:,} korisnika x {stats['n_items']:,} recepata")
    print(f"           gustina = {stats['density'] * 100:.4f}%")
    print(
        f"  po korisniku: min={stats['min_user_positives_final']}, "
        f"prosek={stats['mean_user_positives_final']:.1f}, "
        f"max={stats['max_user_positives_final']}"
    )
    print(
        f"  po receptu  : min={stats['min_item_positives_final']}, "
        f"prosek={stats['mean_item_positives_final']:.1f}, "
        f"max={stats['max_item_positives_final']}"
    )
    print("-" * 68)
    print(f"  index.json     -> {config.INDEX_JSON}")
    print(f"  stats.json     -> {config.STATS_JSON}")
    print(f"  positives.npz  -> {config.POSITIVES_NPZ}")
    print("=" * 68)


# ---------------------------------------------------------------------- load


def load_positives() -> PositiveData:
    """Load the cached, already-encoded positives.  Fails loudly if absent."""
    if not config.POSITIVES_NPZ.exists() or not config.INDEX_JSON.exists():
        raise SystemExit(
            "GRESKA: obradjeni podaci ne postoje.\nPokrenite prvo: uv run python -m foodrec.data"
        )
    users, items = load_index_pair(config.INDEX_JSON)
    with np.load(config.POSITIVES_NPZ) as payload:
        user_idx = payload["user_idx"].astype(np.int32, copy=False)
        item_idx = payload["item_idx"].astype(np.int32, copy=False)

    # Cheap but decisive guard: no index may point outside the frozen mapping.
    if user_idx.size and (user_idx.max() >= len(users) or item_idx.max() >= len(items)):
        raise SystemExit(
            "GRESKA: kesirani indeksi ne odgovaraju index.json - obrisite ai/data/processed/."
        )

    stats = {}
    if config.STATS_JSON.exists():
        stats = json.loads(config.STATS_JSON.read_text(encoding="utf-8"))
    return PositiveData(user_idx, item_idx, users, items, stats)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m foodrec.data",
        description="Priprema Food.com podataka za implicitni feedback.",
    )
    parser.add_argument(
        "--datasets-dir",
        default=None,
        help=f"Direktorijum sa RAW_*.csv (podrazumevano {config.DATASETS_DIR}).",
    )
    args = parser.parse_args(argv)
    build_dataset(args.datasets_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
