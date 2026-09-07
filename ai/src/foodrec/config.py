"""Central configuration for the recommender pipeline.

Every path used by the pipeline is derived here, so no module has to guess where
the repository root is.  Kept free of heavy imports (torch, pandas) on purpose:
`foodrec.serving` runs inside the FastAPI process and must stay lightweight.
"""

from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path

# ai/src/foodrec/config.py -> foodrec -> src -> ai -> repository root
REPO_ROOT = Path(os.environ.get("FOODREC_ROOT", Path(__file__).resolve().parents[3]))

# Raw Kaggle CSVs ("Food.com Recipes and Interactions").  Overridable so the
# development/synthetic run can point somewhere outside the repository.
DATASETS_DIR = Path(os.environ.get("FOODREC_DATASETS_DIR", REPO_ROOT / "datasets"))
RAW_RECIPES = DATASETS_DIR / "RAW_recipes.csv"
RAW_INTERACTIONS = DATASETS_DIR / "RAW_interactions.csv"

AI_DIR = REPO_ROOT / "ai"
PROCESSED_DIR = Path(os.environ.get("FOODREC_PROCESSED_DIR", AI_DIR / "data" / "processed"))
ARTIFACTS_DIR = Path(os.environ.get("FOODREC_ARTIFACTS_DIR", AI_DIR / "artifacts"))
RESULTS_DIR = Path(os.environ.get("FOODREC_RESULTS_DIR", AI_DIR / "results"))

# Files produced by `python -m foodrec.data`
INDEX_JSON = PROCESSED_DIR / "index.json"
STATS_JSON = PROCESSED_DIR / "stats.json"
POSITIVES_NPZ = PROCESSED_DIR / "positives.npz"

# The directory the backend reads (MODEL_ARTIFACT_DIR, default ai/artifacts/mult_vae)
SERVING_DIR = ARTIFACTS_DIR / "mult_vae"

SEED = 42

# Implicit feedback definition, agreed with the thesis supervisor.
POSITIVE_THRESHOLD = 4  # rating >= 4 is a positive; rating 0 means "review, no rating"
MIN_USER_POSITIVES = 3
MIN_ITEM_POSITIVES = 5

# Split proportions (weak generalization is per-user, strong is per-user-group).
TEST_FRACTION = 0.20
VAL_FRACTION = 0.10
STRONG_USER_FRACTION = 0.10
STRONG_FOLD_IN_FRACTION = 0.80

TOP_KS = (10, 20)
COVERAGE_K = 20

MODEL_KEYS = ("popularity", "itemknn", "ease", "multdae", "multvae", "neumf")

DATASET_MISSING_MESSAGE = """\
GRESKA: Food.com dataset nije pronadjen.

Ocekivane datoteke:
  {recipes}
  {interactions}

Preuzmite skup podataka "Food.com Recipes and Interactions" sa Kaggle-a
(https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions)
i raspakujte RAW_recipes.csv i RAW_interactions.csv u direktorijum:
  {datasets_dir}

Alternativno, zadajte drugu putanju preko --datasets-dir ili promenljive
okruzenja FOODREC_DATASETS_DIR.
"""


def dataset_missing_message(datasets_dir: Path | None = None) -> str:
    """Serbian fail-fast message shown when the raw CSVs are not on disk."""
    directory = Path(datasets_dir) if datasets_dir is not None else DATASETS_DIR
    return DATASET_MISSING_MESSAGE.format(
        recipes=directory / "RAW_recipes.csv",
        interactions=directory / "RAW_interactions.csv",
        datasets_dir=directory,
    )


def ensure_dirs() -> None:
    for directory in (PROCESSED_DIR, ARTIFACTS_DIR, RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def set_seed(seed: int = SEED) -> None:
    """Seed every RNG the pipeline touches.  torch is imported lazily."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # pragma: no cover - numpy is a hard dependency
        pass
    try:
        import torch

        torch.manual_seed(seed)
        if torch.backends.mps.is_available():
            torch.mps.manual_seed(seed)
    except ImportError:
        pass  # serving-only environments do not ship torch


def get_device(preference: str = "auto"):
    """Resolve a torch device.  `auto` prefers MPS on Apple silicon."""
    import torch

    preference = (preference or "auto").lower()
    if preference == "cpu":
        return torch.device("cpu")
    if preference == "mps":
        if not torch.backends.mps.is_available():
            raise SystemExit("GRESKA: MPS nije dostupan na ovoj masini (koristite --device cpu).")
        return torch.device("mps")
    if preference != "auto":
        raise SystemExit(f"GRESKA: nepoznat uredjaj {preference!r} (auto|cpu|mps).")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def git_commit() -> str:
    """Short commit hash, recorded in every results JSON for traceability."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def library_versions() -> dict[str, str]:
    """Versions recorded in the exported config.json (thesis reproducibility)."""
    import platform

    versions = {"python": platform.python_version()}
    for module_name in ("numpy", "scipy", "pandas", "sklearn", "torch"):
        try:
            module = __import__(module_name)
        except ImportError:
            continue
        versions[module_name] = getattr(module, "__version__", "unknown")
    return versions
