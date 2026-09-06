"""FastAPI aplikacija - minimalni bootstrap nad PostgreSQL bazom."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.db.session import verify_database

# TODO: Sledeci workstream pise nove rutere nad SQLAlchemy slojem i
# registruje ih ovde. Stari ruteri (auth, users, recipes, recommendations)
# jos uvek importuju obrisane database.py / auth_database.py, pa bi srusili
# start aplikacije - zato su namerno iskljuceni:
#
# from backend.app.routers.auth import router as auth_router
# from backend.app.routers.users import router as users_router
# from backend.app.routers.recipes import router as recipes_router
# from backend.app.routers.recommendations import router as recommendations_router

logger = logging.getLogger(__name__)

MODEL_MULT_VAE = "mult_vae"
MODEL_POPULARITY = "popularity"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) Baza mora biti dostupna i mora biti prava baza.
    verify_database()
    logger.info("Baza je dostupna (foodrec).")

    # 2) Model je opcion - aplikacija mora da se podigne i bez njega.
    #    foodrec.serving jos ne postoji (pise ga AI workstream).
    try:
        from foodrec.serving import Recommender

        app.state.recommender = Recommender.load(settings.model_artifact_dir)
        logger.info("Ucitan MultVAE model iz %s", settings.model_artifact_dir)
    except Exception as exc:  # noqa: BLE001 - namerno siroko, model je opcion
        app.state.recommender = None
        logger.warning("Model nije ucitan (%s). Aplikacija radi sa popularity fallback-om.", exc)

    yield


app = FastAPI(
    title="Food Recommendation System API",
    description="Backend API za sistem preporuke recepata",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TODO: ovde idu app.include_router(...) pozivi nakon prepisivanja rutera.


def _active_model(app: FastAPI) -> str:
    return MODEL_MULT_VAE if getattr(app.state, "recommender", None) else MODEL_POPULARITY


@app.get("/")
def root():
    return {
        "name": "Food Recommendation System API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    try:
        verify_database()
        db_status = "ok"
    except Exception:
        # Health endpoint ne sme da pukne - greska se prijavljuje u odgovoru.
        logger.exception("Health check: baza nije dostupna")
        db_status = "error"

    return {
        "status": "ok",
        "db": db_status,
        "model": _active_model(app),
    }
