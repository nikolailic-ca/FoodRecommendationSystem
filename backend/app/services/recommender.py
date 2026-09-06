"""Sloj preporuka: MultVAE model kada je dostupan, popularnost kao fallback.

Ruter iznad ovog modula je namerno tanak - sva logika (maske, rangiranje,
objasnjenja, dopuna stranice) zivi ovde.

O modelu se pretpostavlja samo ono sto je dogovoreno sa AI workstream-om:

    recommender.item_index.ids            -> id-jevi recepata u katalogu modela
    recommender.score(positive_ids)       -> niz ocena poravnat sa item_index.ids
    recommender.explain(rec_id, rated_ids)-> objasnjenje ili None

Sve preko toga se hvata i pretvara u fallback, da neuskladjena verzija
modela ne obori API.
"""

import logging
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
from sqlalchemy import Integer, all_, func, literal, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import Recipe, RecipeTag, Tag, User, UserRating
from backend.app.services.recipes import (
    candidate_query,
    count_candidates,
    load_recipes_in_order,
    to_card,
)

logger = logging.getLogger(__name__)

MODEL_MULT_VAE = "mult_vae"
MODEL_POPULARITY = "popularity"

# Prozor u kome match_percent uopste ima smisla. Bez ovoga bi kod 40k recepata
# prvih deset stavki bilo "99.9%" i znacka ne bi znacila nista.
MATCH_TOP_K = 200
MATCH_MIN = 60
MATCH_MAX = 99
# Stavke iza prozora dobijaju fiksnu, vidno nizu vrednost.
MATCH_TAIL = 55

# Kategorije za onboarding - redosled odredjuje i prioritet kod dedupliciranja.
ONBOARDING_CATEGORIES: tuple[str, ...] = (
    "chicken",
    "beef",
    "pork",
    "seafood",
    "vegetarian",
    "pasta",
    "desserts",
    "soups-stews",
    "salads",
    "breakfast",
    "30-minutes-or-less",
    "pizza",
    "mexican",
    "asian",
    "italian",
)
ONBOARDING_POPULARITY_LIMIT = 5000
ONBOARDING_PER_CATEGORY_POOL = 10
ONBOARDING_PER_CATEGORY = 2


# --------------------------------------------------------------- match_percent


def match_percent_from_scores(sorted_scores: np.ndarray, positions: Sequence[int]) -> list[int]:
    """Min-max normalizacija preko prvih MATCH_TOP_K ocena, u opseg 60-99.

    `sorted_scores` su ocene kandidata sortirane opadajuce, `positions` su
    indeksi (0-baziran rang) stavki za koje racunamo znacku.
    """
    window = sorted_scores[:MATCH_TOP_K]
    if window.size == 0:
        return [MATCH_TAIL for _ in positions]

    high = float(window[0])
    low = float(window[-1])
    span = high - low

    result: list[int] = []
    for rank in positions:
        if rank >= MATCH_TOP_K or rank >= sorted_scores.size:
            result.append(MATCH_TAIL)
            continue
        if span <= 0:
            result.append(MATCH_MAX)
            continue
        share = (float(sorted_scores[rank]) - low) / span
        result.append(round(MATCH_MIN + (MATCH_MAX - MATCH_MIN) * share))
    return result


def match_percent_from_rank(rank: int, total: int) -> int:
    """Znacka za popularity putanju - tu je jedini signal pozicija u listi."""
    if rank >= MATCH_TOP_K or rank >= total:
        return MATCH_TAIL
    span = min(MATCH_TOP_K, total) - 1
    if span <= 0:
        return MATCH_MAX
    return round(MATCH_MAX - (MATCH_MAX - MATCH_MIN) * rank / span)


# --------------------------------------------------------------- pomocne


def _catalog_ids(recommender: Any) -> np.ndarray | None:
    """id-jevi recepata koje model poznaje, ili None ako model nije upotrebljiv."""
    if recommender is None:
        return None
    try:
        ids = np.asarray(recommender.item_index.ids)
    except Exception:  # noqa: BLE001 - model je opcion, greska znaci fallback
        logger.warning("Model nema upotrebljiv item_index.ids, koristi se popularity.")
        return None
    return ids if ids.size else None


def _user_ratings(db: Session, user_id: int) -> tuple[list[int], list[int], dict[int, int]]:
    """Vraca (svi ocenjeni id-jevi, pozitivni id-jevi, mapa ocena)."""
    rows = db.execute(
        select(UserRating.recipe_id, UserRating.rating)
        .where(UserRating.user_id == user_id)
        .order_by(UserRating.updated_at.desc())
    ).all()

    rated_ids = [recipe_id for recipe_id, _ in rows]
    positive_ids = [
        recipe_id for recipe_id, rating in rows if rating >= settings.positive_rating_threshold
    ]
    return rated_ids, positive_ids, {recipe_id: rating for recipe_id, rating in rows}


def _total_recipes(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Recipe)) or 0


def _explanation_parts(raw: Any) -> tuple[int, float] | None:
    """Svodi izlaz modela na (because_recipe_id, similarity).

    Prihvata dict ili par, jer `foodrec.serving` jos nije napisan.
    """
    if raw is None:
        return None

    recipe_id: Any = None
    similarity: Any = None

    if isinstance(raw, dict):
        for key in ("because_recipe_id", "recipe_id", "id"):
            if raw.get(key) is not None:
                recipe_id = raw[key]
                break
        for key in ("similarity", "score", "weight"):
            if raw.get(key) is not None:
                similarity = raw[key]
                break
    elif isinstance(raw, (tuple, list)) and len(raw) >= 2:
        recipe_id, similarity = raw[0], raw[1]

    if recipe_id is None:
        return None

    try:
        return int(recipe_id), float(similarity) if similarity is not None else 0.0
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------- popularity


def _popularity_page(
    db: Session,
    *,
    user_id: int,
    filters: dict,
    limit: int,
    offset: int,
    exclude_catalog: np.ndarray | None = None,
) -> tuple[list[int], dict[int, int]]:
    """Stranica kandidata poredjanih po popularity_rank.

    `exclude_catalog` se koristi kada popunjavamo rep liste receptima koje
    model uopste ne poznaje. Niz ide kao JEDAN bind parametar (`<> ALL`),
    da 40k id-jeva ne bi zavrsilo kao 40k placeholdera u IN listi.
    """
    if limit <= 0:
        return [], {}

    stmt = candidate_query(db, exclude_user_id=user_id, **filters)
    if exclude_catalog is not None and exclude_catalog.size:
        stmt = stmt.where(
            Recipe.id != all_(literal([int(i) for i in exclude_catalog], ARRAY(Integer)))
        )

    rows = db.execute(
        select(Recipe.id, Recipe.popularity_rank)
        .where(Recipe.id.in_(stmt))
        .order_by(Recipe.popularity_rank)
        .limit(limit)
        .offset(offset)
    ).all()

    return [recipe_id for recipe_id, _ in rows], {recipe_id: rank for recipe_id, rank in rows}


def _popularity_response(
    db: Session,
    *,
    user_id: int,
    filters: dict,
    n: int,
    offset: int,
) -> dict:
    stmt = candidate_query(db, exclude_user_id=user_id, **filters)
    total_candidates = count_candidates(db, stmt)

    page_ids, ranks = _popularity_page(db, user_id=user_id, filters=filters, limit=n, offset=offset)
    recipes = load_recipes_in_order(db, page_ids)

    total_recipes = _total_recipes(db) or 1
    items = []
    for position, recipe in enumerate(recipes):
        rank = ranks.get(recipe.id, total_recipes)
        items.append(
            {
                "recipe": to_card(recipe),
                "score": round(1.0 - (rank - 1) / total_recipes, 6),
                "match_percent": match_percent_from_rank(offset + position, total_candidates),
                "explanation": None,
            }
        )

    return {
        "model": MODEL_POPULARITY,
        "total_candidates": total_candidates,
        "items": items,
    }


# --------------------------------------------------------------- model


def _allowed_mask(
    db: Session,
    *,
    ids: np.ndarray,
    filters: dict,
    rated_ids: Sequence[int],
) -> np.ndarray:
    """Boolean maska nad item_index.ids: sta sme da udje u preporuke."""
    has_filter = any(value for value in filters.values())

    if has_filter:
        # SQL upit se pokrece samo ako filter zaista postoji - inace je
        # ceo katalog dozvoljen i upit bi bio cist gubitak.
        allowed_ids = db.scalars(candidate_query(db, **filters)).all()
        allowed = np.isin(ids, np.asarray(allowed_ids, dtype=ids.dtype))
    else:
        allowed = np.ones(ids.shape, dtype=bool)

    if rated_ids:
        allowed &= ~np.isin(ids, np.asarray(rated_ids, dtype=ids.dtype))

    return allowed


def _model_explanations(
    recommender: Any,
    recipe_ids: Sequence[int],
    rated_ids: Sequence[int],
) -> dict[int, tuple[int, float]]:
    """Objasnjenje po preporuci; greska modela znaci samo izostanak objasnjenja."""
    result: dict[int, tuple[int, float]] = {}
    explain = getattr(recommender, "explain", None)
    if explain is None:
        return result

    for recipe_id in recipe_ids:
        try:
            parts = _explanation_parts(explain(int(recipe_id), list(rated_ids)))
        except Exception:  # objasnjenje je ukras, ne sme da obori odgovor
            logger.warning("Neuspelo objasnjenje za recept %s", recipe_id, exc_info=True)
            continue
        if parts is not None:
            result[int(recipe_id)] = parts

    return result


def _model_response(
    db: Session,
    *,
    recommender: Any,
    ids: np.ndarray,
    user_id: int,
    positive_ids: Sequence[int],
    rated_ids: Sequence[int],
    ratings: dict[int, int],
    filters: dict,
    n: int,
    offset: int,
) -> dict:
    scores = np.asarray(recommender.score(list(positive_ids)), dtype=float).ravel().copy()
    if scores.shape[0] != ids.shape[0]:
        raise ValueError(
            f"Model je vratio {scores.shape[0]} ocena za katalog od {ids.shape[0]} recepata."
        )

    allowed = _allowed_mask(db, ids=ids, filters=filters, rated_ids=rated_ids)
    scores[~allowed] = -np.inf
    total_candidates = int(allowed.sum())

    # argsort nad -scores je rastuci po -score, tj. opadajuci po score;
    # -(-inf) = +inf, pa zabranjene stavke same padaju na kraj.
    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]

    start = min(offset, total_candidates)
    end = min(offset + n, total_candidates)
    page_positions = list(range(start, end))
    page_ids = [int(ids[order[position]]) for position in page_positions]

    explanations = _model_explanations(recommender, page_ids, rated_ids)

    # Jedan IN upit za sve recepte sa stranice I sve recepte iz objasnjenja.
    because_ids = [because_id for because_id, _ in explanations.values()]
    wanted = load_recipes_in_order(db, page_ids + because_ids)
    by_id = {recipe.id: recipe for recipe in wanted}

    percents = match_percent_from_scores(sorted_scores, page_positions)

    items = []
    for position, recipe_id, percent in zip(page_positions, page_ids, percents, strict=True):
        recipe = by_id.get(recipe_id)
        if recipe is None:
            # Model poznaje recept koji vise nije u bazi - preskacemo ga.
            continue

        explanation = None
        parts = explanations.get(recipe_id)
        if parts is not None:
            because = by_id.get(parts[0])
            if because is not None:
                explanation = {
                    "because_recipe_id": because.id,
                    "because_recipe_name": because.name,
                    "because_rating": ratings.get(because.id, 0),
                    "similarity": round(float(parts[1]), 6),
                }

        items.append(
            {
                "recipe": to_card(recipe),
                "score": round(float(sorted_scores[position]), 6),
                "match_percent": percent,
                "explanation": explanation,
            }
        )

    # Dopuna: kada model nema dovoljno kandidata, ostatak stranice popunjavamo
    # popularnim receptima VAN kataloga modela, u istom obliku odgovora.
    missing = n - len(items)
    if missing > 0:
        pad_offset = max(0, offset - total_candidates)
        pad_ids, ranks = _popularity_page(
            db,
            user_id=user_id,
            filters=filters,
            limit=missing,
            offset=pad_offset,
            exclude_catalog=ids,
        )
        total_recipes = _total_recipes(db) or 1
        for recipe in load_recipes_in_order(db, pad_ids):
            rank = ranks.get(recipe.id, total_recipes)
            items.append(
                {
                    "recipe": to_card(recipe),
                    "score": round(1.0 - (rank - 1) / total_recipes, 6),
                    "match_percent": MATCH_TAIL,
                    "explanation": None,
                }
            )

    return {
        "model": MODEL_MULT_VAE,
        "total_candidates": total_candidates,
        "items": items,
    }


def recommend_for_user(
    db: Session,
    *,
    user: User,
    recommender: Any,
    n: int,
    offset: int,
    name: str | None = None,
    max_minutes: int | None = None,
    ingredients: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
) -> dict:
    """Glavni ulaz za GET /recommendations/me."""
    filters = {
        "query": name,
        "max_minutes": max_minutes,
        "ingredients": list(ingredients or []),
        "tags": list(tags or []),
    }

    rated_ids, positive_ids, ratings = _user_ratings(db, user.id)
    ids = _catalog_ids(recommender)

    known_positive: list[int] = []
    if ids is not None and positive_ids:
        mask = np.isin(np.asarray(positive_ids, dtype=ids.dtype), ids)
        known_positive = [int(pid) for pid, keep in zip(positive_ids, mask, strict=True) if keep]

    if ids is None or not known_positive:
        # Model nije ucitan ili korisnik jos nema pozitivnu ocenu koju model
        # prepoznaje - jedini posten signal je popularnost.
        return _popularity_response(db, user_id=user.id, filters=filters, n=n, offset=offset)

    try:
        return _model_response(
            db,
            recommender=recommender,
            ids=ids,
            user_id=user.id,
            positive_ids=known_positive,
            rated_ids=rated_ids,
            ratings=ratings,
            filters=filters,
            n=n,
            offset=offset,
        )
    except Exception:  # model ne sme da obori endpoint
        logger.exception("Model je pukao pri skorovanju, prelazak na popularity.")
        return _popularity_response(db, user_id=user.id, filters=filters, n=n, offset=offset)


# --------------------------------------------------------------- slicni recepti


def similar_from_model(
    db: Session, *, recommender: Any, recipe_id: int, n: int
) -> list[dict] | None:
    """Slicni recepti preko modela; None znaci "koristi tag fallback"."""
    ids = _catalog_ids(recommender)
    if ids is None:
        return None

    position = np.flatnonzero(ids == recipe_id)
    if position.size == 0:
        return None

    try:
        scores = np.asarray(recommender.score([int(recipe_id)]), dtype=float).ravel().copy()
        if scores.shape[0] != ids.shape[0]:
            return None
    except Exception:  # model je opcion, greska znaci fallback
        logger.warning("Model nije uspeo da skoruje slicne za recept %s", recipe_id, exc_info=True)
        return None

    scores[position[0]] = -np.inf

    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]
    positions = [p for p in range(min(n, ids.size)) if np.isfinite(sorted_scores[p])]

    page_ids = [int(ids[order[p]]) for p in positions]
    # Ista normalizacija kao za match_percent, samo skalirana na 0-1.
    percents = match_percent_from_scores(sorted_scores, positions)

    recipes = load_recipes_in_order(db, page_ids)
    by_id = {recipe.id: recipe for recipe in recipes}

    result = []
    for recipe_id_out, percent in zip(page_ids, percents, strict=True):
        recipe = by_id.get(recipe_id_out)
        if recipe is not None:
            result.append({"recipe": to_card(recipe), "similarity": round(percent / 100, 4)})
    return result


def similar_by_tags(db: Session, *, recipe: Recipe, n: int) -> list[dict]:
    """Fallback: recepti koji dele bar jedan od 5 najredjih tagova ovog recepta.

    Najredji tagovi nose najvise informacije - 'dessert' spaja pola dataseta,
    'thai' skoro nikoga.
    """
    rare_tags = list(
        db.scalars(
            select(RecipeTag.tag)
            .join(Tag, Tag.tag == RecipeTag.tag)
            .where(RecipeTag.recipe_id == recipe.id)
            .order_by(Tag.recipe_count.asc().nulls_last(), RecipeTag.tag)
            .limit(5)
        ).all()
    )
    if not rare_tags:
        return []

    shared = (
        select(RecipeTag.recipe_id.label("recipe_id"), func.count().label("shared"))
        .where(RecipeTag.tag.in_(rare_tags), RecipeTag.recipe_id != recipe.id)
        .group_by(RecipeTag.recipe_id)
        .subquery()
    )

    rows = db.execute(
        select(shared.c.recipe_id, shared.c.shared)
        .join(Recipe, Recipe.id == shared.c.recipe_id)
        .order_by(shared.c.shared.desc(), Recipe.popularity_rank)
        .limit(n)
    ).all()

    shared_by_id = {recipe_id: count for recipe_id, count in rows}
    recipes = load_recipes_in_order(db, [recipe_id for recipe_id, _ in rows])

    return [
        {
            "recipe": to_card(item),
            # Deljenje sa brojem posmatranih tagova (5 u punom slucaju).
            "similarity": round(shared_by_id[item.id] / len(rare_tags), 4),
        }
        for item in recipes
    ]


# --------------------------------------------------------------- onboarding

_ONBOARDING_SQL = text(
    """
    WITH categories(tag, position) AS (
        SELECT * FROM unnest(CAST(:tags AS text[])) WITH ORDINALITY AS t(tag, position)
    ),
    matched AS (
        SELECT DISTINCT ON (rt.recipe_id)
               rt.recipe_id                AS recipe_id,
               c.tag                       AS tag,
               c.position                  AS position,
               r.popularity_rank           AS popularity_rank,
               (ri.url IS NULL)            AS no_image
        FROM categories c
        JOIN recipe_tags rt ON rt.tag = c.tag
        JOIN recipes r ON r.id = rt.recipe_id
        LEFT JOIN recipe_images ri ON ri.recipe_id = r.id
        WHERE r.popularity_rank <= :popularity_limit
        ORDER BY rt.recipe_id, c.position
    ),
    ranked AS (
        SELECT recipe_id, tag, position,
               row_number() OVER (
                   PARTITION BY tag ORDER BY no_image, popularity_rank
               ) AS rn
        FROM matched
    )
    SELECT recipe_id, tag
    FROM ranked
    WHERE rn <= :pool
    ORDER BY position, rn
    """
)


def build_onboarding_cards(db: Session, recommender: Any) -> list[dict]:
    """Recepti za onboarding: 2 po kategoriji, isprepletani do 30 kartica.

    Kada je model ucitan, kandidati se suzavaju na katalog modela. Bez toga bi
    onboarding ocene zavrsile na receptima koje model nikada nije video, pa bi
    svaki novi korisnik zauvek ostao na popularity fallback-u.
    """
    rows = db.execute(
        _ONBOARDING_SQL,
        {
            "tags": list(ONBOARDING_CATEGORIES),
            "popularity_limit": ONBOARDING_POPULARITY_LIMIT,
            "pool": ONBOARDING_PER_CATEGORY_POOL,
        },
    ).all()

    pools: dict[str, list[int]] = {tag: [] for tag in ONBOARDING_CATEGORIES}
    for recipe_id, tag in rows:
        pools[tag].append(int(recipe_id))

    empty = [tag for tag, pool in pools.items() if not pool]
    if empty:
        logger.warning("Onboarding kategorije bez recepata u bazi: %s", ", ".join(empty))

    ids = _catalog_ids(recommender)
    if ids is not None:
        catalog = set(ids.tolist())
        pools = {tag: [i for i in pool if i in catalog] for tag, pool in pools.items()}

    chosen = {tag: pool[:ONBOARDING_PER_CATEGORY] for tag, pool in pools.items()}

    # Preplitanje: prvo po jedan iz svake kategorije, pa drugi krug.
    ordered_ids: list[int] = []
    for slot in range(ONBOARDING_PER_CATEGORY):
        for tag in ONBOARDING_CATEGORIES:
            pool = chosen[tag]
            if slot < len(pool):
                ordered_ids.append(pool[slot])

    return [to_card(recipe) for recipe in load_recipes_in_order(db, ordered_ids)]


def missing_onboarding_tags(db: Session, categories: Iterable[str] | None = None) -> list[str]:
    """Kategorije iz ONBOARDING_CATEGORIES kojih nema u tabeli `tags`."""
    wanted = list(categories or ONBOARDING_CATEGORIES)
    present = set(db.scalars(select(Tag.tag).where(Tag.tag.in_(wanted))).all())
    return [tag for tag in wanted if tag not in present]
