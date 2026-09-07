"""Zajednicki sloj nad receptima: serijalizacija i upit nad kandidatima.

Rutere namerno drzimo tanke - i lista recepata i preporuke koriste isti
`candidate_query`, pa filteri svuda znace potpuno istu stvar.
"""

from collections.abc import Iterable, Sequence

from sqlalchemy import Select, func, intersect, select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import Recipe, RecipeIngredient, RecipeTag, UserFavorite, UserRating
from backend.app.services.text import clean_name, meaningful_tags, normalize_ingredient

CARD_TAG_LIMIT = 4
DESCRIPTION_SHORT_LIMIT = 110

# Znakovi koje LIKE/ILIKE tumaci kao dzokere - beze se pre ubacivanja u sablon.
# Javno je jer svaki `.like(..., escape=...)` mora da koristi bas ovaj znak.
LIKE_ESCAPE = "\\"


def escape_like(value: str) -> str:
    """Priprema korisnicki unos za LIKE sablon (escape za \\, % i _)."""
    out = value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    out = out.replace("%", f"{LIKE_ESCAPE}%")
    return out.replace("_", f"{LIKE_ESCAPE}_")


def short_description(description: str | None, limit: int = DESCRIPTION_SHORT_LIMIT) -> str:
    """Skracuje opis na granici reci, na otprilike `limit` karaktera."""
    text = clean_name(description)
    if not text or len(text) <= limit:
        return text

    cut = text[:limit].rstrip()
    space = cut.rfind(" ")
    # Ako bi rez po reci pojeo pola teksta, radije secemo po karakteru.
    if space > limit // 2:
        cut = cut[:space]

    return cut.rstrip(" ,.;:-") + "…"


def to_card(recipe: Recipe) -> dict:
    """RecipeCard - oblik koji frontend koristi svuda gde prikazuje listu."""
    image = recipe.image
    return {
        "id": recipe.id,
        "name": recipe.name,
        "minutes": recipe.minutes,
        "n_ingredients": recipe.n_ingredients,
        "n_steps": recipe.n_steps,
        "calories": recipe.calories,
        "rating_count": recipe.rating_count,
        "avg_rating": recipe.avg_rating,
        "image_url": image.url if image is not None else None,
        "tags": meaningful_tags(recipe.tags or [], limit=CARD_TAG_LIMIT),
        "description_short": short_description(recipe.description),
    }


def to_detail(recipe: Recipe, user_rating: int | None, is_favorite: bool) -> dict:
    """RecipeDetail - kartica prosirena svime sto ide na stranicu recepta."""
    image = recipe.image
    image_out = None
    # url je NULL kada je Pexels pretraga obavljena ali fotografija nije nadjena.
    if image is not None and image.url:
        image_out = {
            "url": image.url,
            "photographer": image.photographer,
            "photographer_url": image.photographer_url,
            "source_url": image.source_url,
        }

    return {
        **to_card(recipe),
        "description": recipe.description,
        "steps": [str(step) for step in recipe.steps or []],
        "ingredients": [str(item) for item in recipe.ingredients or []],
        # Isti filter kao na kartici, samo bez ogranicenja na cetiri taga.
        # Sirovi tagovi bi ovde pocinjali strukturnim tagom ("course",
        # "time-to-make"), pa bi frontend za isti recept birao jedan placeholder
        # na mrezi a drugi na njegovoj stranici.
        "tags": meaningful_tags(recipe.tags or [], limit=None),
        "nutrition": {
            "calories": recipe.calories,
            "total_fat_pdv": recipe.total_fat_pdv,
            "sugar_pdv": recipe.sugar_pdv,
            "sodium_pdv": recipe.sodium_pdv,
            "protein_pdv": recipe.protein_pdv,
            "saturated_fat_pdv": recipe.saturated_fat_pdv,
            "carbohydrates_pdv": recipe.carbohydrates_pdv,
        },
        "submitted": recipe.submitted,
        "image": image_out,
        "user_rating": user_rating,
        "is_favorite": is_favorite,
    }


def normalize_tags(tags: Iterable[str] | None) -> list[str]:
    """Mala slova, bez praznih i bez duplikata - onako kako su tagovi u bazi."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        tag = str(raw).strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def candidate_query(
    db: Session,  # deo javnog potpisa; sam upit se gradi bez sesije
    *,
    query: str | None = None,
    max_minutes: int | None = None,
    ingredients: Iterable[str] | None = None,
    tags: Iterable[str] | None = None,
    exclude_user_id: int | None = None,
) -> Select:
    """Gradi `SELECT recipes.id` sa svim aktivnim filterima.

    Rezultat je Select nad kojim pozivalac sam radi count/order/limit,
    pa isti filteri vaze i za listu recepata i za preporuke.
    """
    stmt = select(Recipe.id)

    if query:
        term = query.strip()
        if term:
            # GIN trigram indeks nad recipes.name pokriva i '%...%' oblik.
            stmt = stmt.where(Recipe.name.ilike(f"%{escape_like(term)}%", escape=LIKE_ESCAPE))

    if max_minutes is not None:
        stmt = stmt.where(Recipe.minutes.is_not(None), Recipe.minutes <= max_minutes)

    ingredient_selects = []
    for raw in ingredients or []:
        # Isti normalizator kao u ETL-u, inace se upit i baza ne bi poklopili.
        _, tokens = normalize_ingredient(raw)
        if tokens:
            ingredient_selects.append(
                select(RecipeIngredient.recipe_id).where(RecipeIngredient.tokens.contains(tokens))
            )

    if ingredient_selects:
        # tokens @> ARRAY['egg'] hvata 'egg' i 'egg whites', ali ne i 'eggplant'
        # (to je jedan token 'eggplant'). INTERSECT daje I-vezu izmedju termina.
        combined = (
            ingredient_selects[0]
            if len(ingredient_selects) == 1
            else intersect(*ingredient_selects)
        )
        stmt = stmt.where(Recipe.id.in_(combined))

    wanted_tags = normalize_tags(tags)
    if wanted_tags:
        tag_select = (
            select(RecipeTag.recipe_id)
            .where(RecipeTag.tag.in_(wanted_tags))
            .group_by(RecipeTag.recipe_id)
            .having(func.count() == len(wanted_tags))
        )
        stmt = stmt.where(Recipe.id.in_(tag_select))

    if exclude_user_id is not None:
        stmt = stmt.where(
            Recipe.id.not_in(
                select(UserRating.recipe_id).where(UserRating.user_id == exclude_user_id)
            )
        )

    return stmt


def count_candidates(db: Session, stmt: Select) -> int:
    """Broj redova koje `candidate_query` vraca (bez limita i offseta)."""
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def load_recipes_in_order(db: Session, recipe_ids: Sequence[int]) -> list[Recipe]:
    """Ucitava recepte JEDNIM upitom i vraca ih u trazenom redosledu.

    Slike se ucitavaju kroz selectin (jedan dodatni upit za ceo skup),
    tako da nema N+1 upita po kartici.
    """
    if not recipe_ids:
        return []

    unique_ids = list(dict.fromkeys(recipe_ids))
    rows = db.scalars(
        select(Recipe).where(Recipe.id.in_(unique_ids)).options(selectinload(Recipe.image))
    ).all()

    by_id = {recipe.id: recipe for recipe in rows}
    return [by_id[recipe_id] for recipe_id in recipe_ids if recipe_id in by_id]


def user_rating_map(db: Session, user_id: int, recipe_ids: Sequence[int]) -> dict[int, int]:
    """{recipe_id: ocena} za zadate recepte, jednim upitom."""
    if not recipe_ids:
        return {}

    rows = db.execute(
        select(UserRating.recipe_id, UserRating.rating).where(
            UserRating.user_id == user_id,
            UserRating.recipe_id.in_(list(set(recipe_ids))),
        )
    ).all()
    return {recipe_id: rating for recipe_id, rating in rows}


def is_favorite(db: Session, user_id: int, recipe_id: int) -> bool:
    return (
        db.scalar(
            select(func.count())
            .select_from(UserFavorite)
            .where(UserFavorite.user_id == user_id, UserFavorite.recipe_id == recipe_id)
        )
        or 0
    ) > 0
