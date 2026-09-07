"""Live inference for the FastAPI backend - numpy only, no torch.

The backend imports this module inside its process, so it must stay cheap and
side-effect free.  Importing it pulls in numpy and json, nothing else; there is
deliberately no `import torch` anywhere in this file or in foodrec.index.

Everything is a pure function over read-only arrays loaded once, which makes the
object thread-safe: the backend loads it in the FastAPI lifespan and every
request only reads.

The one trick worth explaining: the encoder input is a mostly-zero binary vector
divided by its L2 norm, so

    W1 @ (x / ||x||)  ==  (1 / sqrt(k)) * sum of the k rows of W1.T

A dense matrix-vector product against 42k mostly-zero entries would waste almost
all of its work, so `score` gathers those k rows and sums them instead.  The only
full-width operation left is the decoder's output GEMV (hidden x n_items).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from foodrec.index import IndexMapping

# Kept in sync by hand with backend/app/services/recommender.py, which owns the
# canonical copy, so the smoke test shows the badge the API would actually return.
MATCH_TOP_K = 200
MATCH_MIN = 60
MATCH_MAX = 99
MATCH_TAIL = 55

REQUIRED_FILES = ("weights.npz", "item_index.json", "config.json")


def _read_only(array: np.ndarray) -> np.ndarray:
    array = np.ascontiguousarray(array)
    array.flags.writeable = False
    return array


class Recommender:
    """Mult-VAE scoring, item similarity and explanations over the exported artifact."""

    def __init__(
        self,
        item_index: IndexMapping,
        weights: dict[str, np.ndarray],
        item_embeddings: np.ndarray,
        popularity: np.ndarray,
        config: dict,
    ) -> None:
        self.item_index = item_index
        self.config = config
        self.n_items = len(item_index)

        self.enc_1_w_t = _read_only(weights["enc_1_w_t"].astype(np.float32))
        self.enc_1_b = _read_only(weights["enc_1_b"].astype(np.float32))
        self.variational = "enc_2_w" in weights
        if self.variational:
            self.enc_2_w = _read_only(weights["enc_2_w"].astype(np.float32))
            self.enc_2_b = _read_only(weights["enc_2_b"].astype(np.float32))
            self.dec_1_w = _read_only(weights["dec_1_w"].astype(np.float32))
            self.dec_1_b = _read_only(weights["dec_1_b"].astype(np.float32))
            self.latent = self.enc_2_w.shape[0] // 2
        else:
            self.latent = self.enc_1_w_t.shape[1]
        self.dec_2_w = _read_only(weights["dec_2_w"].astype(np.float32))
        self.dec_2_b = _read_only(weights["dec_2_b"].astype(np.float32))

        self.item_embeddings = _read_only(item_embeddings.astype(np.float32))
        self.popularity = _read_only(popularity.astype(np.float32))

        if self.dec_2_w.shape[0] != self.n_items:
            raise ValueError(
                f"Model ima {self.dec_2_w.shape[0]} recepata, a indeks {self.n_items}."
            )

    # ------------------------------------------------------------------ load

    @classmethod
    def load(cls, artifact_dir: str | Path) -> Recommender:
        """Load the exported artifact.

        Raises FileNotFoundError when the directory (or a required file) is
        missing, which is the backend's signal to fall back to popularity.
        """
        directory = Path(artifact_dir)
        if not directory.is_dir():
            raise FileNotFoundError(f"Direktorijum sa modelom ne postoji: {directory}")
        for name in REQUIRED_FILES:
            if not (directory / name).exists():
                raise FileNotFoundError(f"Nedostaje {name} u {directory}")

        item_index = IndexMapping.load(directory / "item_index.json")
        with np.load(directory / "weights.npz") as payload:
            weights = {key: np.array(payload[key], dtype=np.float32) for key in payload.files}

        embeddings_path = directory / "item_embeddings.npy"
        if embeddings_path.exists():
            embeddings = np.load(embeddings_path).astype(np.float32)
        else:  # derive from the decoder if the file is absent
            embeddings = weights["dec_2_w"].astype(np.float32)
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / np.maximum(norms, 1e-9)

        popularity_path = directory / "popularity.npy"
        popularity = (
            np.load(popularity_path).astype(np.float32)
            if popularity_path.exists()
            else np.zeros(len(item_index), dtype=np.float32)
        )
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        return cls(item_index, weights, embeddings, popularity, config)

    # ----------------------------------------------------------------- score

    def encode(self, item_indices: np.ndarray) -> np.ndarray:
        """Latent code mu for a user represented by these item indices."""
        hidden = self.enc_1_w_t[item_indices].sum(axis=0)
        hidden /= np.sqrt(item_indices.shape[0], dtype=np.float32)  # L2 norm of a binary row
        hidden += self.enc_1_b
        np.tanh(hidden, out=hidden)
        if not self.variational:
            return hidden
        projected = self.enc_2_w @ hidden + self.enc_2_b
        return projected[: self.latent]  # mu; logvar is unused at inference

    def score(self, positive_recipe_ids) -> np.ndarray:
        """Scores over the whole catalog, aligned with `item_index.ids`.

        Unknown recipe ids are ignored.  With no known positive left, the honest
        answer is popularity, and that is what the backend expects.
        """
        indices = np.unique(self.item_index.encode(positive_recipe_ids, strict=False))
        if indices.size == 0:
            return self.popularity.copy()
        latent = self.encode(indices)
        if self.variational:
            latent = np.tanh(self.dec_1_w @ latent + self.dec_1_b)
        return self.dec_2_w @ latent + self.dec_2_b

    # --------------------------------------------------------------- similar

    def similar(self, recipe_id: int, n: int = 10) -> list[tuple[int, float]]:
        """The n most similar recipes by cosine over the decoder item embeddings."""
        position = self.item_index.to_idx.get(int(recipe_id))
        if position is None:
            return []
        similarity = self.item_embeddings @ self.item_embeddings[position]
        similarity[position] = -np.inf
        count = min(n, self.n_items - 1)
        if count <= 0:
            return []
        top = np.argpartition(-similarity, kth=count - 1)[:count]
        top = top[np.argsort(-similarity[top], kind="stable")]
        return [(int(self.item_index.ids[i]), float(similarity[i])) for i in top]

    def explain(self, rec_recipe_id: int, rated_recipe_ids) -> tuple[int | None, float]:
        """Which rated recipe best explains this recommendation (nearest neighbour)."""
        position = self.item_index.to_idx.get(int(rec_recipe_id))
        if position is None:
            return None, 0.0
        rated = np.unique(self.item_index.encode(rated_recipe_ids, strict=False))
        rated = rated[rated != position]
        if rated.size == 0:
            return None, 0.0
        similarity = self.item_embeddings[rated] @ self.item_embeddings[position]
        best = int(np.argmax(similarity))
        return int(self.item_index.ids[rated[best]]), float(similarity[best])

    # ------------------------------------------------------------- recommend

    def recommend(
        self,
        positive_recipe_ids,
        n: int = 10,
        exclude_recipe_ids=None,
    ) -> list[dict]:
        """Top-n recommendations with the same match badge the API returns."""
        scores = self.score(positive_recipe_ids)
        seen = list(positive_recipe_ids) + list(exclude_recipe_ids or [])
        if seen:
            scores[self.item_index.encode(seen, strict=False)] = -np.inf

        order = np.argsort(-scores, kind="stable")
        sorted_scores = scores[order]
        count = min(n, int(np.isfinite(sorted_scores).sum()))
        percents = self.match_percent(sorted_scores, range(count))
        return [
            {
                "recipe_id": int(self.item_index.ids[order[rank]]),
                "score": float(sorted_scores[rank]),
                "match_percent": percents[rank],
                "rank": rank + 1,
            }
            for rank in range(count)
        ]

    @staticmethod
    def match_percent(sorted_scores: np.ndarray, positions) -> list[int]:
        """Min-max normalisation over the top-200 window into 60-99.

        Deliberately identical to `match_percent_from_scores` in
        backend/app/services/recommender.py, down to the edge cases: the window is
        a positional PREFIX truncated to the number of finite scores (not a
        filtered slice, which would pull later finite values in and move `low`),
        and the tail cutoff compares the rank against that finite count (not
        against the full array length, which would compute a share from a -inf
        score).  Excluded items carry -inf and sort to the end.

        The two implementations are kept in sync by hand; this is the copy that
        the smoke test exercises, and the backend owns the canonical one.
        """
        sorted_scores = np.asarray(sorted_scores)
        positions = list(positions)
        # Finite values are a prefix of the array (argsort keeps them ahead of
        # -inf and NaN), so a prefix slice is enough.
        candidates = int(np.isfinite(sorted_scores).sum())
        window = sorted_scores[: min(MATCH_TOP_K, candidates)]
        if window.size == 0:
            return [MATCH_TAIL for _ in positions]

        high, low = float(window[0]), float(window[-1])
        span = high - low

        result: list[int] = []
        for rank in positions:
            if rank >= MATCH_TOP_K or rank >= candidates:
                result.append(MATCH_TAIL)
            elif span <= 0:
                result.append(MATCH_MAX)
            else:
                share = (float(sorted_scores[rank]) - low) / span
                result.append(round(MATCH_MIN + (MATCH_MAX - MATCH_MIN) * share))
        return result


# ------------------------------------------------------------------ smoke test


def _smoke(artifact_dir: Path, repeats: int = 200, seed: int = 42) -> int:
    import sys

    print("=" * 68)
    print("SMOKE TEST SERVIRANJA")
    print("=" * 68)
    print(f"  artefakt: {artifact_dir}")
    try:
        started = time.perf_counter()
        recommender = Recommender.load(artifact_dir)
        load_seconds = time.perf_counter() - started
    except FileNotFoundError as error:
        print(f"  GRESKA: {error}")
        print("  Pokrenite: uv run python -m foodrec.train --model multvae --full")
        return 1

    print(f"  ucitavanje: {load_seconds * 1000:.0f} ms, {recommender.n_items:,} recepata, "
          f"latent={recommender.latent}")
    print(f"  torch ucitan u procesu: {'torch' in sys.modules}")

    rng = np.random.default_rng(seed)
    popular = np.argsort(-recommender.popularity, kind="stable")[:200]
    history_idx = rng.choice(popular, size=min(5, popular.shape[0]), replace=False)
    history = [int(recommender.item_index.ids[i]) for i in history_idx]
    print(f"  istorija (5 recepata): {history}")

    recommender.score(history)  # warm-up, so the timing excludes first-touch page faults
    durations = []
    for _ in range(repeats):
        started = time.perf_counter()
        recommender.score(history)
        durations.append((time.perf_counter() - started) * 1000.0)
    durations = np.asarray(durations)
    print(
        f"  score(): srednje {durations.mean():.2f} ms, medijana {np.median(durations):.2f} ms, "
        f"p95 {np.percentile(durations, 95):.2f} ms  (n={repeats})"
    )

    print("-" * 68)
    print("  top 10 preporuka:")
    for item in recommender.recommend(history, n=10):
        print(f"    #{item['rank']:<3} recept {item['recipe_id']:<10} "
              f"score={item['score']:8.3f}  match={item['match_percent']}%")

    print("-" * 68)
    print(f"  similar({history[0]}, 5):")
    for recipe_id, similarity in recommender.similar(history[0], 5):
        print(f"    recept {recipe_id:<10} cos={similarity:.4f}")

    print("-" * 68)
    top = recommender.recommend(history, n=1)
    if top:
        because, similarity = recommender.explain(top[0]["recipe_id"], history)
        print(f"  explain({top[0]['recipe_id']}, istorija) -> recept {because}, "
              f"slicnost {similarity:.4f}")
        if because is None or because not in history:
            print("  GRESKA: objasnjenje ne pokazuje na ocenjeni recept.")
            return 1
    print("=" * 68)
    print("  smoke test: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    from foodrec import config

    parser = argparse.ArgumentParser(
        prog="python -m foodrec.serving", description="Provera artefakta za serviranje."
    )
    parser.add_argument("--smoke", action="store_true", help="Pokreni smoke test.")
    parser.add_argument("--artifact-dir", default=str(config.SERVING_DIR))
    parser.add_argument("--repeats", type=int, default=200)
    args = parser.parse_args(argv)

    if not args.smoke:
        parser.print_help()
        return 0
    return _smoke(Path(args.artifact_dir), args.repeats)


if __name__ == "__main__":
    raise SystemExit(main())
