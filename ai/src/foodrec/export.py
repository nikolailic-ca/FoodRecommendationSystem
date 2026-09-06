"""Export the trained Mult-VAE into the serving artifact the backend loads.

    uv run python -m foodrec.export --model multvae

Writes ai/artifacts/mult_vae/ (MODEL_ARTIFACT_DIR):

    model.pt             torch state_dict only, so torch.load(weights_only=True) works
    weights.npz          the same tensors laid out for the numpy runtime
    item_embeddings.npy  decoder output rows, L2-normalised, float16
    item_index.json      the frozen id <-> index mapping
    popularity.npy       positive counts per item, aligned to the index
    config.json          architecture, hyperparameters, metrics, versions, commit

The encoder's first weight matrix is stored TRANSPOSED, (n_items, hidden).  The
serving path never multiplies a mostly-zero input vector by it - it gathers the
rows of the user's positives and sums them, which is the same arithmetic at a
fraction of the cost.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np

from foodrec import config
from foodrec.data import load_positives
from foodrec.models.multvae import MultVAE
from foodrec.train import artifact_dir


def _numpy_weights(state: dict) -> dict[str, np.ndarray]:
    """torch state_dict -> the arrays foodrec.serving expects."""
    arrays: dict[str, np.ndarray] = {}
    # Linear(in, out).weight has shape (out, in).
    arrays["enc_1_w_t"] = np.ascontiguousarray(
        state["enc_1.weight"].numpy().T.astype(np.float32)
    )  # (n_items, hidden) - gathered by row at serving time
    arrays["enc_1_b"] = state["enc_1.bias"].numpy().astype(np.float32)
    if "enc_2.weight" in state:
        arrays["enc_2_w"] = state["enc_2.weight"].numpy().astype(np.float32)
        arrays["enc_2_b"] = state["enc_2.bias"].numpy().astype(np.float32)
        arrays["dec_1_w"] = state["dec_1.weight"].numpy().astype(np.float32)
        arrays["dec_1_b"] = state["dec_1.bias"].numpy().astype(np.float32)
    arrays["dec_2_w"] = np.ascontiguousarray(state["dec_2.weight"].numpy().astype(np.float32))
    arrays["dec_2_b"] = state["dec_2.bias"].numpy().astype(np.float32)
    return arrays


def export_multvae(
    source: Path | None = None,
    destination: Path | None = None,
    seed: int = config.SEED,
) -> Path:
    import torch

    source = Path(source) if source is not None else _pick_source()
    destination = Path(destination) if destination is not None else config.SERVING_DIR
    destination.mkdir(parents=True, exist_ok=True)

    model = MultVAE.load(source)
    data = load_positives()
    if len(data.items) != model.n_items:
        raise SystemExit(
            f"GRESKA: model ima {model.n_items} recepata, a index.json {len(data.items)}. "
            "Model i mapiranje nisu iz istog prolaza - ponovo pokrenite data/split/train."
        )

    state = {key: value.detach().cpu() for key, value in model.net.state_dict().items()}
    torch.save(state, destination / "model.pt")

    arrays = _numpy_weights(state)
    np.savez(destination / "weights.npz", **arrays)

    # Item embeddings = decoder output rows, L2-normalised (cosine == dot product).
    embeddings = arrays["dec_2_w"]
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    np.maximum(norms, 1e-9, out=norms)
    np.save(destination / "item_embeddings.npy", (embeddings / norms).astype(np.float16))

    data.items.save(destination / "item_index.json")

    popularity = np.asarray(data.matrix().sum(axis=0), dtype=np.float32).ravel()
    np.save(destination / "popularity.npy", popularity)

    results_path = config.RESULTS_DIR / "multvae.json"
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}

    payload = {
        "model": "mult_vae",
        "architecture": {
            "n_items": model.n_items,
            "hidden": model.hidden,
            "latent": model.latent,
            "variational": model.variational,
            "activation": "tanh",
            "input": "L2-normalised binary implicit feedback",
            "encoder": [
                f"Linear({model.n_items}, {model.hidden})",
                "tanh",
                f"Linear({model.hidden}, {2 * model.latent})  -> mu, logvar",
            ],
            "decoder": [
                f"Linear({model.latent}, {model.hidden})",
                "tanh",
                f"Linear({model.hidden}, {model.n_items})",
            ],
            "inference": "mu, dropout off",
        },
        "hyperparams": model.hyperparams(),
        "seed": seed,
        "best_epoch": results.get("best_epoch"),
        "trained_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "trained_on": "all positives (train + validation + test + strong users)",
        "source_artifact": str(source),
        "dataset_stats": data.stats,
        "metrics": {
            "weak": results.get("weak", "nepoznato"),
            "strong": results.get("strong", "nepoznato"),
            "note": "metrike su sa podele, ne sa finalnog modela treniranog na svim podacima",
        },
        "git_commit": config.git_commit(),
        "library_versions": config.library_versions(),
        "files": {
            "model.pt": "torch state_dict (weights_only=True kompatibilan)",
            "weights.npz": "isti tenzori za numpy runtime (enc_1_w_t je transponovan)",
            "item_embeddings.npy": "float16, L2-normalizovani redovi izlaznog sloja dekodera",
            "item_index.json": "zamrznuto mapiranje id recepta -> indeks",
            "popularity.npy": "broj pozitivnih ocena po receptu, poravnat sa indeksom",
        },
    }
    (destination / "config.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    total = sum(path.stat().st_size for path in destination.iterdir() if path.is_file())
    print("=" * 68)
    print("IZVOZ MODELA ZA SERVIRANJE")
    print("=" * 68)
    print(f"  izvor      : {source}")
    print(f"  odrediste  : {destination}")
    for path in sorted(destination.iterdir()):
        if path.is_file():
            print(f"    {path.name:<22} {path.stat().st_size / 1024:>10,.0f} KB")
    print(f"  ukupno     : {total / 1024 / 1024:.1f} MB")
    print(f"  recepti    : {model.n_items:,}")
    print("=" * 68)
    return destination


def _pick_source() -> Path:
    """Prefer the model refit on all positives; fall back to the split model."""
    full = artifact_dir("multvae", full=True)
    if (full / "meta.json").exists():
        return full
    split = artifact_dir("multvae")
    if (split / "meta.json").exists():
        print("  UPOZORENJE: koristi se model treniran samo na podeli "
              "(pokrenite --full za finalni model).")
        return split
    raise SystemExit(
        "GRESKA: Mult-VAE nije istreniran.\n"
        "Pokrenite: uv run python -m foodrec.train --model multvae && "
        "uv run python -m foodrec.train --model multvae --full"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m foodrec.export", description="Izvoz Mult-VAE modela za FastAPI backend."
    )
    parser.add_argument("--model", default="multvae", choices=["multvae"])
    parser.add_argument("--source", default=None, help="Direktorijum sa istreniranim modelom.")
    parser.add_argument("--dest", default=None, help=f"Podrazumevano {config.SERVING_DIR}.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    args = parser.parse_args(argv)

    export_multvae(source=args.source, destination=args.dest, seed=args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
