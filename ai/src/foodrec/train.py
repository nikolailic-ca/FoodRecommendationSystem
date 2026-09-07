"""Train one model on the shared split.

    uv run python -m foodrec.train --model multvae --device auto
    uv run python -m foodrec.train --model ease            # own process, ~9 GB peak
    uv run python -m foodrec.train --model multvae --full  # refit on everything + export

Every model sees exactly the same `train` matrix and the same validation view,
so the comparison table in ai/results/summary.md is apples to apples.

`--full` refits the model on ALL positives (train + validation + test + the
strong-generalization users) for the number of epochs that early stopping picked
on the split, and then exports the serving artifact.  This is the model that
ships; the split-trained one is the model that gets reported.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from foodrec import config
from foodrec.data import load_positives
from foodrec.models import MODEL_KEYS, NEEDS_TORCH, build_model
from foodrec.split import load_splits


def artifact_dir(model_key: str, full: bool = False) -> Path:
    return config.ARTIFACTS_DIR / (f"{model_key}_full" if full else model_key)


def _model_kwargs(model_key: str, args) -> dict:
    kwargs: dict = {}
    if model_key == "ease":
        if args.max_items is not None:
            kwargs["max_items"] = args.max_items
        if args.ease_lambda is not None:
            kwargs["reg"] = args.ease_lambda
    if model_key == "itemknn":
        if args.knn_block is not None:
            kwargs["block"] = args.knn_block
        if args.knn_k is not None:
            kwargs["k"] = args.knn_k
        if args.knn_shrinkage is not None:
            kwargs["shrinkage"] = args.knn_shrinkage
    return kwargs


def _resolve_device(model_key: str, preference: str) -> str:
    if model_key not in NEEDS_TORCH:
        return "cpu"
    return str(config.get_device(preference))


def _best_epoch_from_results(model_key: str) -> int | None:
    results_file = config.RESULTS_DIR / f"{model_key}.json"
    if results_file.exists():
        payload = json.loads(results_file.read_text(encoding="utf-8"))
        if payload.get("best_epoch"):
            return int(payload["best_epoch"])
    meta_file = artifact_dir(model_key) / "meta.json"
    if meta_file.exists():
        payload = json.loads(meta_file.read_text(encoding="utf-8"))
        if payload.get("best_epoch"):
            return int(payload["best_epoch"])
    return None


def train_split_model(model_key: str, args) -> Path:
    splits = load_splits(args.seed)
    config.set_seed(args.seed)
    device = _resolve_device(model_key, args.device)

    print("=" * 68)
    print(f"TRENIRANJE: {model_key}  (seed={args.seed}, uredjaj={device})")
    print("=" * 68)
    print(
        f"  train: {splits.train.nnz:,} interakcija, "
        f"{splits.n_users:,} korisnika x {splits.n_items:,} recepata"
    )
    if model_key == "ease":
        gigabytes = splits.n_items * splits.n_items * 4 / 2**30
        print(f"  UPOZORENJE: EASE alocira gustu matricu ~{gigabytes:.1f} GB "
              f"(vrhunac ~{gigabytes * 1.3:.1f} GB). Ne pokretati uz MPS posao.")

    model = build_model(model_key, splits.n_items, **_model_kwargs(model_key, args))
    started = time.perf_counter()
    model.fit(
        splits.train,
        val_input=splits.train,
        val_target=splits.weak_val,
        val_users=splits.weak_users,
        seed=args.seed,
        device=device,
        verbose=True,
    )
    elapsed = time.perf_counter() - started
    if not model.train_time_s:
        model.train_time_s = elapsed

    directory = artifact_dir(model_key)
    model.save(directory)
    print("-" * 68)
    print(f"  trajanje treninga: {model.train_time_s:.1f} s")
    if model.best_epoch:
        print(f"  najbolja epoha   : {model.best_epoch}")
    print(f"  sacuvano         -> {directory}")
    print("=" * 68)
    return directory


def train_full_model(model_key: str, args) -> Path:
    """Refit on every positive interaction for the epoch count chosen on the split."""
    data = load_positives()
    config.set_seed(args.seed)
    device = _resolve_device(model_key, args.device)
    best_epoch = _best_epoch_from_results(model_key)

    print("=" * 68)
    print(f"FINALNO TRENIRANJE NA SVIM PODACIMA: {model_key} (uredjaj={device})")
    print("=" * 68)
    full = data.matrix()
    print(f"  sve pozitivne interakcije: {full.nnz:,}")
    if model_key in NEEDS_TORCH:
        if best_epoch is None:
            raise SystemExit(
                f"GRESKA: nema zabelezene najbolje epohe za {model_key}.\n"
                f"Pokrenite prvo: uv run python -m foodrec.train --model {model_key} "
                f"i uv run python -m foodrec.evaluate --model {model_key}"
            )
        print(f"  broj epoha (iz ai/results/{model_key}.json): {best_epoch}")

    model = build_model(model_key, data.n_items, **_model_kwargs(model_key, args))
    started = time.perf_counter()
    model.fit(full, seed=args.seed, device=device, verbose=True, max_epochs=best_epoch)
    if not model.train_time_s:
        model.train_time_s = time.perf_counter() - started

    directory = artifact_dir(model_key, full=True)
    model.save(directory)
    print("-" * 68)
    print(f"  trajanje: {model.train_time_s:.1f} s")
    print(f"  sacuvano -> {directory}")
    print("=" * 68)

    if model_key in ("multvae", "multdae"):
        from foodrec.export import export_multvae

        export_multvae(source=directory, seed=args.seed, model_key=model_key)
    else:
        print(f"  (izvoz je definisan za multvae/multdae; {model_key} je sacuvan bez izvoza)")
    return directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m foodrec.train", description="Treniranje jednog modela na zajednickoj podeli."
    )
    parser.add_argument("--model", required=True, choices=list(MODEL_KEYS))
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "mps"])
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Refit na svim pozitivnim interakcijama za zabelezeni broj epoha, pa izvoz.",
    )
    parser.add_argument("--max-items", type=int, default=None, help="Samo EASE: ogranicenje kataloga.")
    parser.add_argument("--knn-block", type=int, default=None, help="Samo ItemKNN: velicina bloka kolona.")
    parser.add_argument("--knn-k", type=int, default=None, help="Samo ItemKNN: broj suseda.")
    parser.add_argument("--knn-shrinkage", type=float, default=None, help="Samo ItemKNN: prigusenje.")
    parser.add_argument("--ease-lambda", type=float, default=None, help="Samo EASE: regularizacija.")
    args = parser.parse_args(argv)

    config.ensure_dirs()
    if args.full:
        train_full_model(args.model, args)
    else:
        train_split_model(args.model, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
