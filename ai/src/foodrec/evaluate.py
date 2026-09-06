"""Evaluate trained models in both views and render the thesis comparison table.

    uv run python -m foodrec.evaluate --model all --summary

Writes ai/results/<model>.json per model and ai/results/summary.md, and refuses
to finish quietly if the sanity checks in foodrec.metrics fail - a model that
ranks at chance level must never end up in a results table by accident.
"""

from __future__ import annotations

import argparse
import json
import time

from foodrec import config
from foodrec.metrics import evaluate_ranking, random_score_expectation, sanity_check
from foodrec.models import DISPLAY_NAMES, MODEL_KEYS, get_model_class
from foodrec.split import Splits, load_splits
from foodrec.train import artifact_dir

METRIC_COLUMNS = ("recall@10", "recall@20", "ndcg@10", "ndcg@20", "coverage@20")


class _TimedScorer:
    """Wraps a model scorer to measure real per-user scoring cost."""

    def __init__(self, model, X_input) -> None:
        self.inner = model.scorer(X_input)
        self.seconds = 0.0
        self.users = 0

    def __call__(self, rows):
        started = time.perf_counter()
        scores = self.inner(rows)
        self.seconds += time.perf_counter() - started
        self.users += len(rows)
        return scores

    @property
    def ms_per_user(self) -> float:
        return 1000.0 * self.seconds / max(1, self.users)


def evaluate_model(model_key: str, splits: Splits, verbose: bool = True) -> dict:
    model_class = get_model_class(model_key)
    directory = artifact_dir(model_key)
    model = model_class.load(directory)

    if verbose:
        print(f"  [{model_key}] weak generalizacija ({splits.weak_users.shape[0]:,} korisnika)...")
    weak_scorer = _TimedScorer(model, splits.train)
    weak = evaluate_ranking(
        weak_scorer,
        mask=splits.weak_mask,
        target=splits.weak_test,
        users=splits.weak_users,
        ks=config.TOP_KS,
        coverage_k=config.COVERAGE_K,
        batch_size=model.score_batch_size,
    )

    strong: dict | str
    if model.supports_strong:
        if verbose:
            print(
                f"  [{model_key}] strong generalizacija "
                f"({splits.strong_users.shape[0]:,} nevidjenih korisnika)..."
            )
        strong = evaluate_ranking(
            model.scorer(splits.strong_input),
            mask=splits.strong_input,
            target=splits.strong_target,
            users=splits.strong_users,
            ks=config.TOP_KS,
            coverage_k=config.COVERAGE_K,
            batch_size=model.score_batch_size,
        )
    else:
        strong = "N/A"
        if verbose:
            print(f"  [{model_key}] strong generalizacija: N/A (model nema red za novog korisnika)")

    meta_path = directory / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    payload = {
        "model": model_key,
        "display_name": DISPLAY_NAMES[model_key],
        "seed": splits.seed,
        "git_commit": config.git_commit(),
        "dataset_stats": splits.meta.get("dataset_stats", {}),
        "split": {
            key: value
            for key, value in splits.meta.items()
            if key not in ("dataset_stats",)
        },
        "hyperparams": meta.get("hyperparams", {}),
        "best_epoch": meta.get("best_epoch"),
        "train_time_s": meta.get("train_time_s", 0.0),
        "score_ms_per_user": round(weak_scorer.ms_per_user, 4),
        "supports_strong": model.supports_strong,
        "training_history": meta.get("history", []),
        "weak": weak,
        "strong": strong,
    }

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.RESULTS_DIR / f"{model_key}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return payload


def load_results() -> dict[str, dict]:
    results: dict[str, dict] = {}
    for key in MODEL_KEYS:
        path = config.RESULTS_DIR / f"{key}.json"
        if path.exists():
            results[key] = json.loads(path.read_text(encoding="utf-8"))
    return results


def _row(view, columns=METRIC_COLUMNS) -> str:
    if not isinstance(view, dict):
        return " | ".join(["N/A"] * len(columns))
    return " | ".join(f"{view.get(column, float('nan')):.4f}" for column in columns)


def render_summary(results: dict[str, dict]) -> str:
    if not results:
        raise SystemExit("GRESKA: nema rezultata u ai/results/ - pokrenite evaluaciju.")

    any_result = next(iter(results.values()))
    stats = any_result.get("dataset_stats", {})
    split = any_result.get("split", {})
    n_items = int(split.get("n_items", stats.get("n_items", 1)))
    random_floor = random_score_expectation(n_items, 20)

    lines: list[str] = []
    lines.append("# Rezultati poredjenja modela")
    lines.append("")
    lines.append(
        f"Podaci: {stats.get('n_positives', 0):,} pozitivnih interakcija "
        f"({stats.get('n_users', 0):,} korisnika x {stats.get('n_items', 0):,} recepata), "
        f"pozitivna ocena >= {stats.get('positive_threshold', 4)}, "
        f"k-core (korisnik >= {stats.get('kcore', {}).get('min_user_positives', '?')}, "
        f"recept >= {stats.get('kcore', {}).get('min_item_positives', '?')})."
    )
    lines.append("")
    lines.append(
        f"Seed: {any_result.get('seed')} | commit: `{any_result.get('git_commit')}` | "
        f"weak korisnici: {split.get('n_weak_users', 0):,} | "
        f"strong korisnici: {split.get('n_strong_users', 0):,}"
    )
    lines.append("")
    lines.append("## Weak generalizacija (primarni pogled)")
    lines.append("")
    lines.append("Svi korisnici su u treningu; 20% njihovih pozitivnih interakcija je izdvojeno za test.")
    lines.append("")
    lines.append("| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |")
    lines.append("|---|---|---|---|---|---|")
    for key in MODEL_KEYS:
        if key not in results:
            continue
        lines.append(f"| {DISPLAY_NAMES[key]} | {_row(results[key].get('weak'))} |")
    lines.append(
        f"| _slucajno rangiranje_ | {10 / n_items:.4f} | {random_floor:.4f} | "
        f"{10 / n_items:.4f} | {random_floor:.4f} | - |"
    )
    lines.append("")
    lines.append("## Strong generalizacija (hladan start)")
    lines.append("")
    lines.append(
        "10% korisnika nikada nije bilo u treningu; 80% njihovih interakcija se ubacuje "
        "kao ulaz, 20% su ciljevi. NeuMF ovo ne moze - nema red u tabeli korisnickih "
        "ugradjivanja za nepoznatog korisnika."
    )
    lines.append("")
    lines.append("| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |")
    lines.append("|---|---|---|---|---|---|")
    for key in MODEL_KEYS:
        if key not in results:
            continue
        lines.append(f"| {DISPLAY_NAMES[key]} | {_row(results[key].get('strong'))} |")
    lines.append("")
    lines.append("## Cena treniranja i skorovanja")
    lines.append("")
    lines.append("| Model | Najbolja epoha | Trening (s) | Skorovanje (ms/korisnik) |")
    lines.append("|---|---|---|---|")
    for key in MODEL_KEYS:
        if key not in results:
            continue
        payload = results[key]
        epoch = payload.get("best_epoch") or "-"
        lines.append(
            f"| {DISPLAY_NAMES[key]} | {epoch} | {payload.get('train_time_s', 0):.1f} | "
            f"{payload.get('score_ms_per_user', 0):.3f} |"
        )
    lines.append("")
    lines.append(
        "Skorovanje je mereno nad celim katalogom po korisniku, na istom uredjaju na kome je "
        "model treniran. Razlika izmedju NeuMF-a i Mult-VAE je sustinska: Mult-VAE skoruje ceo "
        "katalog jednim prolazom kroz mrezu, dok NeuMF mora da provuce svaki par (korisnik, "
        "recept) kroz MLP."
    )
    lines.append("")
    return "\n".join(lines)


def print_table(results: dict[str, dict]) -> None:
    header = f"{'model':<12} " + " ".join(f"{column:>12}" for column in METRIC_COLUMNS)
    print("=" * len(header))
    print("WEAK GENERALIZACIJA")
    print("=" * len(header))
    print(header)
    for key in MODEL_KEYS:
        if key not in results:
            continue
        view = results[key].get("weak", {})
        row = " ".join(f"{view.get(column, float('nan')):>12.4f}" for column in METRIC_COLUMNS)
        print(f"{key:<12} {row}")
    print()
    print("=" * len(header))
    print("STRONG GENERALIZACIJA")
    print("=" * len(header))
    print(header)
    for key in MODEL_KEYS:
        if key not in results:
            continue
        view = results[key].get("strong")
        if not isinstance(view, dict):
            print(f"{key:<12} " + " ".join(f"{'N/A':>12}" for _ in METRIC_COLUMNS))
            continue
        row = " ".join(f"{view.get(column, float('nan')):>12.4f}" for column in METRIC_COLUMNS)
        print(f"{key:<12} {row}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m foodrec.evaluate",
        description="Evaluacija modela u oba pogleda i generisanje ai/results/summary.md.",
    )
    parser.add_argument("--model", default="all", choices=["all", *MODEL_KEYS])
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--summary", action="store_true", help="Ispisi ai/results/summary.md.")
    parser.add_argument(
        "--no-sanity",
        action="store_true",
        help="Preskoci provere zdravog razuma (samo za dijagnostiku).",
    )
    args = parser.parse_args(argv)

    config.ensure_dirs()
    splits = load_splits(args.seed)
    keys = list(MODEL_KEYS) if args.model == "all" else [args.model]

    print("=" * 68)
    print(f"EVALUACIJA (seed={args.seed})")
    print("=" * 68)
    missing: list[str] = []
    for key in keys:
        if not (artifact_dir(key) / "meta.json").exists():
            missing.append(key)
            continue
        evaluate_model(key, splits)

    if missing:
        print(f"  preskoceno (nije istrenirano): {', '.join(missing)}")

    results = load_results()
    print()
    print_table(results)
    print()

    problems = sanity_check(results, splits.n_items, strict=not args.no_sanity)
    if not problems:
        print("  provere zdravog razuma: OK")

    if args.summary:
        text = render_summary(results)
        path = config.RESULTS_DIR / "summary.md"
        path.write_text(text, encoding="utf-8")
        print(f"  summary -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
