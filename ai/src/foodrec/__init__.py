"""foodrec - recommender pipeline for the Food.com dataset.

Modules:
    config      paths, seed, device resolution
    index       the frozen id <-> matrix-index mapping (numpy only)
    data        raw CSVs -> filtered implicit feedback, index-encoded
    split       one split, two evaluation views
    metrics     ranking metrics and cross-model sanity checks
    models      popularity, itemknn, ease, multdae, multvae, neumf
    train       CLI: train one model on the shared split
    evaluate    CLI: both views + ai/results/summary.md
    export      CLI: serving artifact for the FastAPI backend
    serving     live inference, numpy only - imported inside the API process

Nothing here imports torch at package level: `from foodrec.serving import
Recommender` must stay cheap for the backend.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
