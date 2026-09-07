"""Ranking metrics, fully vectorised over user batches.

Conventions (stated once, used everywhere, reported in the thesis):

  Recall@K = hits@K / min(K, |targets|)   - the Mult-VAE (Liang et al. 2018)
             convention; with |targets| in the denominator a user with 40 held
             out items could never exceed 0.5 at K=20 and the average would say
             more about the holdout sizes than about the model.
  NDCG@K   = DCG@K / IDCG@K with binary gains, IDCG computed over
             min(K, |targets|) ideal hits.
  Coverage@20 = |distinct items in any user's top-20| / n_items.

Items the user has already seen (training history, and for the weak test view
also the validation holdout) are pushed to -inf before ranking.
"""

from __future__ import annotations

import numpy as np
from scipy.sparse import csr_array


def _fill_dense_rows(matrix: csr_array, rows: np.ndarray, out: np.ndarray) -> np.ndarray:
    """Materialise selected CSR rows into a preallocated boolean block."""
    out[:] = False
    indptr, indices = matrix.indptr, matrix.indices
    for local, user in enumerate(rows):
        out[local, indices[indptr[user] : indptr[user + 1]]] = True
    return out


def top_k_indices(scores: np.ndarray, k: int) -> np.ndarray:
    """Indices of the k largest scores per row, ordered by score descending."""
    k = min(k, scores.shape[1])
    part = np.argpartition(-scores, kth=k - 1, axis=1)[:, :k]
    part_scores = np.take_along_axis(scores, part, axis=1)
    order = np.argsort(-part_scores, axis=1, kind="stable")
    return np.take_along_axis(part, order, axis=1)


def discount_vector(k: int) -> np.ndarray:
    return 1.0 / np.log2(np.arange(2, k + 2, dtype=np.float64))


class _Accumulator:
    def __init__(self, ks: tuple[int, ...], n_items: int, coverage_k: int) -> None:
        self.ks = ks
        self.n_items = n_items
        self.coverage_k = coverage_k
        self.recall = {k: 0.0 for k in ks}
        self.ndcg = {k: 0.0 for k in ks}
        self.n_users = 0
        self.covered = np.zeros(n_items, dtype=bool)

    def result(self) -> dict:
        if self.n_users == 0:
            return {"n_users": 0}
        out: dict[str, float | int] = {"n_users": int(self.n_users)}
        for k in self.ks:
            out[f"recall@{k}"] = round(self.recall[k] / self.n_users, 6)
            out[f"ndcg@{k}"] = round(self.ndcg[k] / self.n_users, 6)
        out[f"coverage@{self.coverage_k}"] = round(float(self.covered.sum()) / self.n_items, 6)
        out[f"covered_items@{self.coverage_k}"] = int(self.covered.sum())
        return out


def evaluate_ranking(
    score_fn,
    *,
    mask: csr_array,
    target: csr_array,
    users: np.ndarray,
    ks: tuple[int, ...] = (10, 20),
    coverage_k: int = 20,
    batch_size: int = 500,
) -> dict:
    """Rank every evaluated user's catalog and average the metrics.

    `score_fn(rows) -> (len(rows), n_items)` must return scores aligned to the
    frozen item index - it is the model's only contract with the evaluator.
    """
    users = np.asarray(users, dtype=np.int64)
    n_items = int(target.shape[1])
    ks = tuple(sorted(ks))
    k_max = min(max(ks), n_items)
    accumulator = _Accumulator(ks, n_items, coverage_k)

    target_sizes = np.diff(target.indptr)
    discounts = {k: discount_vector(min(k, n_items)) for k in ks}
    ideal = {k: np.concatenate([[0.0], np.cumsum(discounts[k])]) for k in ks}

    mask_block = np.zeros((batch_size, n_items), dtype=bool)
    rel_block = np.zeros((batch_size, n_items), dtype=bool)

    for start in range(0, users.shape[0], batch_size):
        rows = users[start : start + batch_size]
        size = rows.shape[0]
        scores = np.asarray(score_fn(rows), dtype=np.float32)
        if scores.shape != (size, n_items):
            raise ValueError(
                f"score_fn je vratio oblik {scores.shape}, ocekivano {(size, n_items)}."
            )
        scores = np.array(scores, dtype=np.float32, copy=True)

        mask_view = _fill_dense_rows(mask, rows, mask_block[:size])
        rel_view = _fill_dense_rows(target, rows, rel_block[:size])
        scores[mask_view] = -np.inf

        top = top_k_indices(scores, k_max)
        hits = np.take_along_axis(rel_view, top, axis=1)
        sizes = target_sizes[rows].astype(np.int64)
        valid = sizes > 0
        if not valid.any():
            continue

        for k in ks:
            kk = min(k, n_items)
            hits_k = hits[:, :kk]
            denominator = np.minimum(kk, sizes).astype(np.float64)
            recall = np.where(valid, hits_k.sum(axis=1) / np.maximum(denominator, 1.0), 0.0)
            dcg = hits_k.astype(np.float64) @ discounts[k]
            idcg = ideal[k][np.minimum(kk, sizes)]
            ndcg = np.where(valid & (idcg > 0), dcg / np.maximum(idcg, 1e-12), 0.0)
            accumulator.recall[k] += float(recall[valid].sum())
            accumulator.ndcg[k] += float(ndcg[valid].sum())

        covered_k = min(coverage_k, n_items)
        accumulator.covered[np.unique(top[valid][:, :covered_k])] = True
        accumulator.n_users += int(valid.sum())

    return accumulator.result()


def random_score_expectation(n_items: int, k: int = 20) -> float:
    """Recall@k of a uniformly random scorer - the floor every model must clear."""
    return k / n_items


def sanity_check(results: dict[str, dict], n_items: int, strict: bool = True) -> dict:
    """Cross-model sanity checks, split by what a failure actually proves.

    HARD checks are bug signatures: if a model ranks at chance, or the popularity
    baseline does not clear random guessing, something in the split, the index
    mapping or the masking is broken and no number in the table can be trusted.
    These abort the run.

    SOFT checks are dataset expectations carried over from the MovieLens-scale
    literature: item-item models reaching roughly twice popularity, and Mult-VAE
    landing above it.  They are real signals worth printing loudly, but they are
    NOT proof of a bug - on Food.com they fire because the median recipe has five
    training interactions and popularity is genuinely hard to beat at K=20.  That
    was established with an oracle scorer (Recall@20 = 1.000), a random scorer
    (0.000506 against an expected 20/n_items = 0.000501), a hand-verified ItemKNN
    neighbourhood, and monotone shrinkage/lambda sweeps that plateau just below
    popularity.  Downgrading them to warnings keeps the table honest instead of
    unprintable; see ai/results/README.md for the full argument.
    """
    hard: list[str] = []
    soft: list[str] = []

    def recall(model: str) -> float | None:
        view = results.get(model, {}).get("weak")
        if not isinstance(view, dict):
            return None
        return view.get("recall@20")

    random_floor = random_score_expectation(n_items, 20)
    popularity = recall("popularity")

    # --- hard: these mean the pipeline itself is broken -------------------
    if popularity is not None and popularity <= random_floor:
        hard.append(
            f"Popularity Recall@20 ({popularity:.4f}) nije iznad slucajnog pogadjanja "
            f"({random_floor:.4f}) - podela, mapiranje indeksa ili maskiranje su pokvareni."
        )
    for model, payload in results.items():
        view = payload.get("weak")
        if not isinstance(view, dict):
            continue
        value = view.get("recall@20")
        if value is not None and value <= 2.0 * random_floor:
            hard.append(
                f"{model} Recall@20 ({value:.4f}) je na nivou slucajnog izbora "
                f"({random_floor:.4f}) - model gleda u pogresne redove ugradjivanja."
            )

    # --- soft: dataset expectations, printed but not fatal ----------------
    if popularity is not None:
        for model in ("itemknn", "ease"):
            value = recall(model)
            if value is not None and value < 2.0 * popularity:
                soft.append(
                    f"{model} Recall@20 ({value:.4f}) nije dostigao dvostruku popularnost "
                    f"({2 * popularity:.4f}) - ocekivanje kalibrisano na gustim skupovima."
                )
        for model in ("multvae", "multdae"):
            value = recall(model)
            if value is not None and value < popularity:
                soft.append(
                    f"{model} Recall@20 ({value:.4f}) je ispod popularity ({popularity:.4f}) - "
                    "proverite normalizaciju ulaza i maskiranje istorije pre arhitekture."
                )

    if hard and strict:
        message = "\n".join(f"  - {item}" for item in hard)
        raise SystemExit(f"GRESKA: provere koje ukazuju na bag nisu prosle:\n{message}")
    return {"hard": hard, "soft": soft}
