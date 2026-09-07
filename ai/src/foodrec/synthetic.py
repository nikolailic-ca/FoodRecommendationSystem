"""Development aid: a synthetic Food.com-shaped dataset with planted structure.

NOT part of the thesis pipeline and never used for reported results.  It exists
so the whole chain (data -> split -> train -> evaluate -> export -> serving) can
be verified end to end before the real Kaggle download is available, and so that
a regression in the index mapping or the masking shows up as a collapsed metric
instead of a plausible-looking number.

    uv run python -m foodrec.synthetic --out /tmp/foodrec_synth

The planted structure is a set of taste clusters: every user has a primary (and
sometimes a secondary) cluster and draws most of its positives from it, with a
fifth of the interactions drawn uniformly as noise.  A model that learns
co-occurrence must therefore beat popularity by a wide margin; one that silently
scrambles its item indices cannot.

Columns and dtypes match the real RAW_recipes.csv / RAW_interactions.csv,
including the Python-literal list columns and the rating-0 rows (a review
without a rating).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

INGREDIENTS = [
    "chicken",
    "beef",
    "pork",
    "salmon",
    "tofu",
    "rice",
    "pasta",
    "potato",
    "onion",
    "garlic",
    "tomato",
    "basil",
    "olive oil",
    "butter",
    "flour",
    "sugar",
    "eggs",
    "milk",
    "cheese",
    "chocolate",
    "vanilla",
    "cinnamon",
    "paprika",
    "cumin",
    "lemon",
    "lime",
    "soy sauce",
    "ginger",
    "spinach",
    "mushrooms",
    "carrots",
    "beans",
    "yogurt",
    "honey",
    "walnuts",
]
CLUSTER_TAGS = [
    "chicken",
    "beef",
    "pork",
    "seafood",
    "vegetarian",
    "pasta",
    "desserts",
    "soups-stews",
    "salads",
    "breakfast",
    "mexican",
    "asian",
]
BASE_TAGS = ["30-minutes-or-less", "easy", "main-dish", "weeknight", "healthy", "comfort-food"]
VERBS = ["Grilled", "Baked", "Creamy", "Spicy", "Classic", "Quick", "Rustic", "Golden", "Zesty"]
NOUNS = ["casserole", "bake", "stew", "salad", "soup", "pie", "skillet", "bowl", "roast"]


def _recipe_rows(rng: np.random.Generator, n_recipes: int, n_clusters: int):
    """Recipes with non-contiguous ids, so the index mapping is actually exercised."""
    ids = np.sort(rng.choice(np.arange(1000, 900_000), size=n_recipes, replace=False))
    clusters = np.arange(n_recipes) % n_clusters
    rng.shuffle(clusters)
    rows = []
    for position, recipe_id in enumerate(ids):
        cluster = int(clusters[position])
        tag = CLUSTER_TAGS[cluster % len(CLUSTER_TAGS)]
        tags = [tag, *rng.choice(BASE_TAGS, size=2, replace=False).tolist()]
        n_ingredients = int(rng.integers(4, 12))
        ingredients = rng.choice(INGREDIENTS, size=n_ingredients, replace=False).tolist()
        n_steps = int(rng.integers(3, 12))
        steps = [f"step {i + 1}: mix and cook" for i in range(n_steps)]
        nutrition = [round(float(value), 1) for value in rng.uniform(0, 500, size=7)]
        rows.append(
            {
                "name": f"{rng.choice(VERBS)} {tag} {rng.choice(NOUNS)}".lower(),
                "id": int(recipe_id),
                "minutes": int(rng.integers(5, 180)),
                "contributor_id": int(rng.integers(1000, 99_999)),
                "submitted": f"20{rng.integers(5, 18):02d}-{rng.integers(1, 13):02d}-"
                f"{rng.integers(1, 29):02d}",
                "tags": repr(tags),
                "nutrition": repr(nutrition),
                "n_steps": n_steps,
                "steps": repr(steps),
                "description": "synthetic recipe for pipeline verification",
                "ingredients": repr(ingredients),
                "n_ingredients": n_ingredients,
            }
        )
    return ids, clusters, rows


def generate(
    out_dir: Path,
    n_users: int = 3000,
    n_recipes: int = 800,
    n_interactions: int = 60_000,
    n_clusters: int = 12,
    noise: float = 0.20,
    seed: int = 42,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    recipe_ids, clusters, recipe_rows = _recipe_rows(rng, n_recipes, n_clusters)
    user_ids = np.sort(rng.choice(np.arange(10_000, 9_000_000), size=n_users, replace=False))

    # Zipf-ish item popularity, so the popularity baseline is not trivially useless.
    popularity = 1.0 / (1.0 + np.arange(n_recipes)) ** 0.6
    rng.shuffle(popularity)
    by_cluster = [np.flatnonzero(clusters == c) for c in range(n_clusters)]

    primary = rng.integers(0, n_clusters, size=n_users)
    has_secondary = rng.random(n_users) < 0.30
    secondary = rng.integers(0, n_clusters, size=n_users)

    # Interaction counts: lognormal, so a few heavy users exist as in the real data.
    counts = np.clip(
        rng.lognormal(mean=np.log(n_interactions / n_users), sigma=0.6, size=n_users).round(),
        3,
        200,
    ).astype(int)

    rows = []
    for user_position in range(n_users):
        pools = [by_cluster[primary[user_position]]]
        if has_secondary[user_position]:
            pools.append(by_cluster[secondary[user_position]])
        taste = np.unique(np.concatenate(pools))

        count = int(counts[user_position])
        n_noise = round(noise * count)
        n_taste = max(1, count - n_noise)

        taste_weights = popularity[taste] / popularity[taste].sum()
        picked_taste = rng.choice(
            taste, size=min(n_taste, taste.shape[0]), replace=False, p=taste_weights
        )
        all_weights = popularity / popularity.sum()
        picked_noise = rng.choice(
            n_recipes, size=min(n_noise, n_recipes), replace=False, p=all_weights
        )
        picked = np.unique(np.concatenate([picked_taste, picked_noise]))
        in_taste = np.isin(picked, taste)

        for item_position, is_taste in zip(picked, in_taste, strict=True):
            if is_taste:
                # mostly 4-5 (the real data is ~72% five-star), with some 0 reviews
                rating = int(rng.choice([5, 4, 3, 2, 1, 0], p=[0.52, 0.24, 0.09, 0.03, 0.04, 0.08]))
            else:
                rating = int(rng.choice([5, 4, 3, 2, 1, 0], p=[0.12, 0.14, 0.28, 0.19, 0.19, 0.08]))
            rows.append(
                (
                    int(user_ids[user_position]),
                    int(recipe_ids[item_position]),
                    (
                        f"20{rng.integers(8, 19):02d}-{rng.integers(1, 13):02d}-"
                        f"{rng.integers(1, 29):02d}"
                    ),
                    rating,
                    "synthetic review text",
                )
            )

    # A handful of exact duplicates, to exercise the dedup step.
    duplicates = rng.choice(len(rows), size=max(1, len(rows) // 200), replace=False)
    for position in duplicates:
        user_id, recipe_id, date, rating, review = rows[position]
        rows.append((user_id, recipe_id, date, max(0, rating - 1), review))

    recipes_path = out_dir / "RAW_recipes.csv"
    with recipes_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(recipe_rows[0].keys()))
        writer.writeheader()
        writer.writerows(recipe_rows)

    interactions_path = out_dir / "RAW_interactions.csv"
    with interactions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user_id", "recipe_id", "date", "rating", "review"])
        writer.writerows(rows)

    # Ground truth, so the verification script can check that `similar()` stays
    # inside the planted cluster.
    truth_path = out_dir / "ground_truth.npz"
    np.savez(
        truth_path,
        recipe_ids=recipe_ids,
        clusters=clusters,
        user_ids=user_ids,
        primary=primary,
        secondary=np.where(has_secondary, secondary, -1),
    )

    summary = {
        "users": n_users,
        "recipes": n_recipes,
        "interactions": len(rows),
        "clusters": n_clusters,
        "positives": int(sum(1 for row in rows if row[3] >= 4)),
        "zero_rating": int(sum(1 for row in rows if row[3] == 0)),
        "recipes_csv": str(recipes_path),
        "interactions_csv": str(interactions_path),
        "ground_truth": str(truth_path),
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m foodrec.synthetic",
        description="Sinteticki dataset za proveru pipeline-a (razvojna pomoc, ne za rezultate).",
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--users", type=int, default=3000)
    parser.add_argument("--recipes", type=int, default=800)
    parser.add_argument("--interactions", type=int, default=60_000)
    parser.add_argument("--clusters", type=int, default=12)
    parser.add_argument("--noise", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    summary = generate(
        Path(args.out),
        n_users=args.users,
        n_recipes=args.recipes,
        n_interactions=args.interactions,
        n_clusters=args.clusters,
        noise=args.noise,
        seed=args.seed,
    )
    for key, value in summary.items():
        print(f"  {key:<16} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
