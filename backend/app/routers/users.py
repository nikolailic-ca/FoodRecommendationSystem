"""Profil, ocene i omiljeni recepti prijavljenog korisnika.

Stari `/users/{user_id}` endpoint-i nad datasetom su namerno uklonjeni:
korisnici iz Food.com interakcija nisu korisnici aplikacije.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.app.api.deps import CurrentUser, DbSession
from backend.app.core.config import settings
from backend.app.db.models import Recipe, UserFavorite, UserRating
from backend.app.schemas.recipe import RecipeCard
from backend.app.schemas.user import RatingIn, RatingOut, UserOut, UserRatingItem
from backend.app.services.recipes import to_card

router = APIRouter(prefix="/users", tags=["users"])

RecipeId = Annotated[int, Path(description="ID recepta iz dataseta")]


def _no_content() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _ratings_count(db: Session, user_id: int) -> int:
    return (
        db.scalar(select(func.count()).select_from(UserRating).where(UserRating.user_id == user_id))
        or 0
    )


def _require_recipe(db: Session, recipe_id: int) -> None:
    if db.scalar(select(Recipe.id).where(Recipe.id == recipe_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recept {recipe_id} ne postoji.",
        )


@router.get("/me", response_model=UserOut, summary="Podaci o prijavljenom korisniku")
def read_me(db: DbSession, user: CurrentUser) -> dict:
    count = _ratings_count(db, user.id)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at,
        "ratings_count": count,
        "onboarding_completed": count >= settings.onboarding_min_ratings,
    }


@router.get(
    "/me/ratings",
    response_model=list[UserRatingItem],
    summary="Sve ocene korisnika",
)
def read_my_ratings(
    db: DbSession,
    user: CurrentUser,
    min_rating: Annotated[int | None, Query(ge=1, le=5)] = None,
) -> list[dict]:
    stmt = (
        select(UserRating, Recipe)
        .join(Recipe, Recipe.id == UserRating.recipe_id)
        .where(UserRating.user_id == user.id)
    )
    if min_rating is not None:
        stmt = stmt.where(UserRating.rating >= min_rating)

    # Slike se povlace kroz Recipe.image (lazy="selectin") - jedan dodatni upit
    # za ceo skup, bez N+1.
    rows = db.execute(stmt.order_by(UserRating.updated_at.desc(), UserRating.recipe_id)).all()

    return [
        {
            "recipe": to_card(recipe),
            "rating": rating.rating,
            "created_at": rating.created_at,
            "updated_at": rating.updated_at,
        }
        for rating, recipe in rows
    ]


@router.put(
    "/me/ratings/{recipe_id}",
    response_model=RatingOut,
    summary="Upis ili izmena ocene",
)
def upsert_my_rating(
    db: DbSession,
    user: CurrentUser,
    recipe_id: RecipeId,
    payload: RatingIn,
) -> dict:
    _require_recipe(db, recipe_id)

    stmt = (
        pg_insert(UserRating)
        .values(user_id=user.id, recipe_id=recipe_id, rating=payload.rating)
        .on_conflict_do_update(
            index_elements=["user_id", "recipe_id"],
            # created_at ostaje netaknut - menjaju se samo ocena i vreme izmene.
            set_={"rating": payload.rating, "updated_at": func.now()},
        )
        .returning(
            UserRating.recipe_id,
            UserRating.rating,
            UserRating.created_at,
            UserRating.updated_at,
        )
    )
    row = db.execute(stmt).one()
    db.commit()

    return {
        "recipe_id": row.recipe_id,
        "rating": row.rating,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.delete(
    "/me/ratings/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Brisanje ocene (idempotentno)",
)
def delete_my_rating(db: DbSession, user: CurrentUser, recipe_id: RecipeId) -> Response:
    db.execute(
        delete(UserRating).where(UserRating.user_id == user.id, UserRating.recipe_id == recipe_id)
    )
    db.commit()
    return _no_content()


@router.get(
    "/me/favorites",
    response_model=list[RecipeCard],
    summary="Omiljeni recepti",
)
def read_my_favorites(db: DbSession, user: CurrentUser) -> list[dict]:
    rows = db.scalars(
        select(Recipe)
        .join(UserFavorite, UserFavorite.recipe_id == Recipe.id)
        .where(UserFavorite.user_id == user.id)
        .order_by(UserFavorite.created_at.desc(), Recipe.id)
    ).all()
    return [to_card(recipe) for recipe in rows]


@router.put(
    "/me/favorites/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dodavanje u omiljene (idempotentno)",
)
def add_my_favorite(db: DbSession, user: CurrentUser, recipe_id: RecipeId) -> Response:
    _require_recipe(db, recipe_id)

    db.execute(
        pg_insert(UserFavorite)
        .values(user_id=user.id, recipe_id=recipe_id)
        .on_conflict_do_nothing(index_elements=["user_id", "recipe_id"])
    )
    db.commit()
    return _no_content()


@router.delete(
    "/me/favorites/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Uklanjanje iz omiljenih (idempotentno)",
)
def remove_my_favorite(db: DbSession, user: CurrentUser, recipe_id: RecipeId) -> Response:
    db.execute(
        delete(UserFavorite).where(
            UserFavorite.user_id == user.id, UserFavorite.recipe_id == recipe_id
        )
    )
    db.commit()
    return _no_content()
