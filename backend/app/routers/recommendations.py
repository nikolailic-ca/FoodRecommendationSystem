"""Preporuke - tanak sloj nad services/recommender.py."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy.orm import Session

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.schemas.recipe import RecipeCard
from backend.app.schemas.recommendation import RecommendationsResponse
from backend.app.services.recommender import build_onboarding_cards, recommend_for_user

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

CsvList = Annotated[str | None, Query(description="lista razdvojena zarezima")]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def onboarding_cards(request: Request, db: Session) -> list[dict]:
    """Vraca kes iz app.state; prazan kes se ponovo gradi.

    Kes se puni na startu, ali aplikacija se pusta i pre ETL-a - tada je
    rezultat prazan i ne sme da se "zamrzne", pa se pokusava ponovo.
    """
    cached = getattr(request.app.state, "onboarding_cards", None)
    if cached:
        return cached

    cards = build_onboarding_cards(db, getattr(request.app.state, "recommender", None))
    request.app.state.onboarding_cards = cards or None
    return cards


@router.get(
    "/me",
    response_model=RecommendationsResponse,
    summary="Personalizovane preporuke",
)
def recommendations_for_me(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    n: Annotated[int, Query(ge=1, le=50)] = 12,
    offset: Annotated[int, Query(ge=0)] = 0,
    name: Annotated[str | None, Query(max_length=200)] = None,
    max_minutes: Annotated[int | None, Query(ge=1, le=100000)] = None,
    ingredients: CsvList = None,
    tags: CsvList = None,
) -> dict:
    return recommend_for_user(
        db,
        user=user,
        recommender=getattr(request.app.state, "recommender", None),
        n=n,
        offset=offset,
        name=name,
        max_minutes=max_minutes,
        ingredients=_split_csv(ingredients),
        tags=_split_csv(tags),
    )


@router.get(
    "/onboarding",
    response_model=list[RecipeCard],
    summary="Recepti za pocetno ocenjivanje (javno)",
)
def recommendations_onboarding(request: Request, db: DbSession) -> list[dict]:
    return onboarding_cards(request, db)
