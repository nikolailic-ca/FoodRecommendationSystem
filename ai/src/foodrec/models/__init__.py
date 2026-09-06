"""Model registry.

Imports are lazy so that `python -m foodrec.train --model ease` never loads
torch, and the EASE process stays free of a CUDA/MPS context while it holds a
multi-gigabyte dense matrix.
"""

from __future__ import annotations

from foodrec.models.base import BaseModel

MODEL_KEYS = ("popularity", "itemknn", "ease", "multdae", "multvae", "neumf")

DISPLAY_NAMES = {
    "popularity": "Popularity",
    "itemknn": "ItemKNN",
    "ease": "EASE",
    "multdae": "Mult-DAE",
    "multvae": "Mult-VAE",
    "neumf": "NeuMF",
}

#: models that need a torch device
NEEDS_TORCH = ("multdae", "multvae", "neumf")

#: models that can score a user who was never in training
SUPPORTS_STRONG = {
    "popularity": True,
    "itemknn": True,
    "ease": True,
    "multdae": True,
    "multvae": True,
    "neumf": False,
}


def get_model_class(key: str) -> type[BaseModel]:
    if key == "popularity":
        from foodrec.models.popularity import Popularity

        return Popularity
    if key == "itemknn":
        from foodrec.models.itemknn import ItemKNN

        return ItemKNN
    if key == "ease":
        from foodrec.models.ease import EASE

        return EASE
    if key == "multvae":
        from foodrec.models.multvae import MultVAE

        return MultVAE
    if key == "multdae":
        from foodrec.models.multvae import MultDAE

        return MultDAE
    if key == "neumf":
        from foodrec.models.neumf import NeuMF

        return NeuMF
    raise SystemExit(f"GRESKA: nepoznat model {key!r} (dostupni: {', '.join(MODEL_KEYS)}).")


def build_model(key: str, n_items: int, **kwargs) -> BaseModel:
    return get_model_class(key)(n_items, **kwargs)


__all__ = [
    "DISPLAY_NAMES",
    "MODEL_KEYS",
    "NEEDS_TORCH",
    "SUPPORTS_STRONG",
    "BaseModel",
    "build_model",
    "get_model_class",
]
