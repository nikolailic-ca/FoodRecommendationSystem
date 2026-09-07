"""Autocomplete izvori za filtere: sastojci i tagovi."""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from backend.app.api.deps import DbSession
from backend.app.db.models import Ingredient, Tag
from backend.app.services.recipes import LIKE_ESCAPE, escape_like
from backend.app.services.text import normalize_ingredient

router = APIRouter(tags=["catalog"])


@router.get("/ingredients", response_model=list[str], summary="Predlozi sastojaka")
def list_ingredients(
    db: DbSession,
    query: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[str]:
    stmt = select(Ingredient.display_name, Ingredient.name).order_by(
        Ingredient.recipe_count.desc().nulls_last(), Ingredient.name
    )

    if query:
        # ingredients.name je normalizovana fraza, pa i upit mora kroz isti
        # normalizator - inace "Eggs" nikada ne bi pogodilo "egg".
        norm, _ = normalize_ingredient(query)
        if not norm:
            return []
        pattern = escape_like(norm)
        stmt = stmt.where(
            or_(
                Ingredient.name.like(f"{pattern}%", escape=LIKE_ESCAPE),
                Ingredient.name.like(f"% {pattern}%", escape=LIKE_ESCAPE),
            )
        )

    rows = db.execute(stmt.limit(limit)).all()
    return [display or name for display, name in rows]


@router.get("/tags", response_model=list[str], summary="Predlozi tagova")
def list_tags(
    db: DbSession,
    query: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[str]:
    stmt = select(Tag.tag).order_by(Tag.recipe_count.desc().nulls_last(), Tag.tag)

    if query:
        # Tagovi u datasetu su crticama spojeni ("main-dish"), pa korisnicki
        # razmak prevodimo u crticu i trazimo i pocetak reci unutar taga.
        term = " ".join(query.strip().lower().split())
        if not term:
            return []
        pattern = escape_like(term.replace(" ", "-"))
        stmt = stmt.where(
            or_(
                Tag.tag.like(f"{pattern}%", escape=LIKE_ESCAPE),
                Tag.tag.like(f"%-{pattern}%", escape=LIKE_ESCAPE),
            )
        )

    return list(db.scalars(stmt.limit(limit)).all())
