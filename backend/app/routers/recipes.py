"""Pretraga recepata, detalj recepta i slicni recepti."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from backend.app.api.deps import DbSession, OptionalUser
from backend.app.db.models import Recipe
from backend.app.schemas.recipe import RecipeDetail, RecipeListResponse, SimilarRecipe
from backend.app.services.recipes import (
    candidate_query,
    count_candidates,
    is_favorite,
    load_recipes_in_order,
    to_card,
    to_detail,
    user_rating_map,
)
from backend.app.services.recommender import (
    similar_by_tags,
    similar_from_model,
    user_match_percents,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])

RecipeId = Annotated[int, Path(description="ID recepta iz dataseta")]


@router.get("", response_model=RecipeListResponse, summary="Pretraga recepata")
def list_recipes(
    db: DbSession,
    query: Annotated[str | None, Query(max_length=200, description="deo naziva recepta")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    stmt = candidate_query(db, query=query)

    total = count_candidates(db, stmt)
    ids = db.scalars(stmt.order_by(Recipe.popularity_rank).limit(limit).offset(offset)).all()

    return {"total": total, "items": [to_card(r) for r in load_recipes_in_order(db, ids)]}


@router.get("/{recipe_id}", response_model=RecipeDetail, summary="Detalj recepta")
def read_recipe(db: DbSession, user: OptionalUser, recipe_id: RecipeId) -> dict:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe {recipe_id} does not exist.",
        )

    rating = None
    favorite = False
    if user is not None:
        rating = user_rating_map(db, user.id, [recipe_id]).get(recipe_id)
        favorite = is_favorite(db, user.id, recipe_id)

    return to_detail(recipe, rating, favorite)


@router.get(
    "/{recipe_id}/similar",
    response_model=list[SimilarRecipe],
    summary="Slicni recepti",
)
def read_similar(
    request: Request,
    db: DbSession,
    user: OptionalUser,
    recipe_id: RecipeId,
    n: Annotated[int, Query(ge=1, le=50)] = 8,
) -> list[dict]:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe {recipe_id} does not exist.",
        )

    # Model se koristi samo ako je ucitan i ako recept postoji u njegovom katalogu.
    recommender = getattr(request.app.state, "recommender", None)
    from_model = similar_from_model(db, recommender=recommender, recipe_id=recipe_id, n=n)
    items = from_model if from_model is not None else similar_by_tags(db, recipe=recipe, n=n)

    # Znacka poklapanja je odgovor na drugo pitanje od `similarity`: ne "koliko
    # je ovo blizu receptu koji gledam" nego "koliko ce se MENI svideti". Zato
    # se racuna iz ukusa prijavljenog korisnika, i to istom normalizacijom kao
    # na pocetnoj, pa su procenti uporedivi izmedju ekrana. Vazi i za tag
    # fallback: kako su susedi izabrani ne menja koliko odgovaraju korisniku.
    if user is not None and items:
        percents = user_match_percents(
            db,
            recommender=recommender,
            user_id=user.id,
            recipe_ids=[item["recipe"]["id"] for item in items],
        )
        for item in items:
            item["match_percent"] = percents.get(item["recipe"]["id"])

    return items
