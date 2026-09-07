"""Sloj preporuka: MultVAE model kada je dostupan, popularnost kao fallback.

Ruter iznad ovog modula je namerno tanak - sva logika (maske, rangiranje,
objasnjenja, dopuna stranice) zivi ovde.

O modelu se pretpostavlja samo ono sto je dogovoreno sa AI workstream-om:

    recommender.item_index.ids            -> id-jevi recepata u katalogu modela
    recommender.score(positive_ids)       -> niz ocena poravnat sa item_index.ids
    recommender.explain(rec_id, rated_ids)-> objasnjenje ili None
    recommender.similar(rec_id, n)        -> [(recipe_id, kosinus)] ili []

Sve preko toga se hvata i pretvara u fallback, da neuskladjena verzija
modela ne obori API.
"""

import logging
import math
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
from sqlalchemy import Integer, all_, any_, func, literal, select, text
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

# Kategorije za onboarding - redosled odredjuje i prioritet kod dedupliciranja
# (DISTINCT ON dodeljuje recept najranije navedenoj kategoriji).
#
# "30-minutes-or-less" je namerno izbacen: stajao je ispred pizze, mexican,
# asian i italian, pa je svaki brz recept iz tih kuhinja zavrsavao u kanti za
# trajanje i praznio njihove bazene. Trajanje ionako ne nosi informaciju o
# ukusu - services/text.py ga vec odbacuje kao beznacajan tag.
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
    "pizza",
    "mexican",
    "asian",
    "italian",
)
ONBOARDING_POPULARITY_LIMIT = 5000
# Bazen po kategoriji PRE presecanja sa katalogom modela. Namerno je siroko
# postavljen: kada je bio 10, kategorija cijih je deset najpopularnijih recepata
# van kataloga ostajala je bez ijedne kartice.
ONBOARDING_PER_CATEGORY_POOL = 200
ONBOARDING_PER_CATEGORY = 2


# --------------------------------------------------------------- match_percent


def match_percent_from_scores(sorted_scores: np.ndarray, positions: Sequence[int]) -> list[int]:
    """Min-max normalizacija preko prvih MATCH_TOP_K ocena, u opseg 60-99.

    `sorted_scores` su ocene kandidata sortirane opadajuce, `positions` su
    indeksi (0-baziran rang) stavki za koje racunamo znacku.

    Zabranjene stavke nose -inf i sortiranjem padaju na kraj; one se ne smeju
    naci u prozoru, inace bi raspon bio beskonacan i normalizacija bi dala NaN.
    """
    # Konacne vrednosti su prefiks niza (argsort ih drzi ispred -inf i NaN).
    candidates = int(np.isfinite(sorted_scores).sum())
    window = sorted_scores[: min(MATCH_TOP_K, candidates)]
    if window.size == 0:
        return [MATCH_TAIL for _ in positions]

    high = float(window[0])
    low = float(window[-1])
    span = high - low

    result: list[int] = []
    for rank in positions:
        if rank >= MATCH_TOP_K or rank >= candidates:
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


def _existing_recipe_count(db: Session, recipe_ids: Sequence[int]) -> int:
    """Koliko od zadatih id-jeva zaista postoji u tabeli recipes."""
    unique_ids = list(dict.fromkeys(recipe_ids))
    if not unique_ids:
        return 0
    return (
        db.scalar(
            select(func.count())
            .select_from(Recipe)
            .where(Recipe.id == any_(literal(unique_ids, ARRAY(Integer))))
        )
        or 0
    )


def _id_and_similarity(raw: Any) -> tuple[int, float] | None:
    """Svodi par iz modela na (recipe_id, similarity).

    Koriste ga i objasnjenja i lista slicnih recepata. Prihvata dict ili par,
    jer se oblik koji `foodrec.serving` vraca menjao tokom razvoja.
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
            parts = _id_and_similarity(explain(int(recipe_id), list(rated_ids)))
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

    # NaN i +-inf se tretiraju kao da stavka nije dozvoljena. Inace: +inf razvuce
    # min-max raspon u beskonacnost pa match_percent racuna round(nan) i puca,
    # a NaN/-inf na dozvoljenoj stavci udje u telo odgovora, gde FastAPI
    # serijalizuje sa allow_nan=False i vraca 500 koji try/except oko ove
    # funkcije ne moze da uhvati (desava se posle povratka iz nje).
    allowed &= np.isfinite(scores)
    scores[~allowed] = -np.inf

    # Granice stranice moraju da dolaze iz ISTOG broja koji rangiranje koristi:
    # posle maske i filtriranja nekonacnih ocena to je tacno duzina konacnog
    # prefiksa niza `sorted_scores`. Ranije su granice dolazile iz allowed.sum(),
    # pa su pozicije iza prefiksa hvatale bas one stavke koje je maska izbacila
    # (vec ocenjene recepte).
    ranked_count = int(allowed.sum())

    # `total_candidates` znaci isto na obe putanje: koliko recepata prolazi
    # filtere a korisnik ih jos nije ocenio. Model rangira samo podskup koji
    # poznaje, ostatak stranice pokriva dopuna po popularnosti - zato se broj
    # NE sme racunati iz kataloga modela.
    total_candidates = count_candidates(db, candidate_query(db, exclude_user_id=user_id, **filters))

    # argsort nad -scores je rastuci po -score, tj. opadajuci po score;
    # -(-inf) = +inf, pa zabranjene stavke same padaju na kraj.
    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]

    start = min(offset, ranked_count)
    end = min(offset + n, ranked_count)
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
                    # None, a ne 0: "Because you rated X 0 stars" nije recenica.
                    # Model sme da predlozi recept koji korisnik nije ocenio.
                    "because_rating": ratings.get(because.id),
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
        # Koliko je stavki iz modela vec izaslo na ranijim stranicama; sve
        # ostalo do `offset` je bila dopuna, pa odatle nastavljamo. Ranije se
        # racunalo samo iz `offset - total_candidates`, pa je svaka stranica
        # koja izgubi recept (`recipe is None`) ponovo krenula od popularity
        # offseta 0 i vratila iste recepte kao prethodna.
        model_emitted = _existing_recipe_count(
            db, [int(ids[order[position]]) for position in range(start)]
        )
        pad_offset = max(0, offset - model_emitted)
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


def user_match_percents(
    db: Session, *, recommender: Any, user_id: int, recipe_ids: Sequence[int]
) -> dict[int, int]:
    """Znacka "koliko ti se ovo poklapa" za proizvoljan skup recepata.

    Racuna se iz ISTOG vektora ocena i kroz ISTU normalizaciju kao na pocetnoj
    strani, pa su procenti uporedivi izmedju ekrana. Bez toga bi isti recept
    mogao da pise 92% u preporukama i nesto drugo medju slicnim receptima.

    Prazna mapa znaci "bez znacke", i to je normalno stanje, ne greska: model
    nije ucitan, korisnik jos nema pozitivnu ocenu koju model poznaje, ili
    nijedan trazeni recept nije u katalogu.

    Vec ocenjeni recepti se namerno preskacu. Model ih je dobio na ulazu, pa im
    je ocena visoka po konstrukciji - to nije predvidjanje nego odjek ulaza.
    """
    if recommender is None or not recipe_ids:
        return {}

    ids = _catalog_ids(recommender)
    if ids is None:
        return {}

    rated_ids, positive_ids, _ = _user_ratings(db, user_id)
    if not positive_ids:
        return {}

    mask = np.isin(np.asarray(positive_ids, dtype=ids.dtype), ids)
    known_positive = [int(pid) for pid, keep in zip(positive_ids, mask, strict=True) if keep]
    if not known_positive:
        return {}

    try:
        scores = np.asarray(recommender.score(known_positive), dtype=float).ravel().copy()
    except Exception:  # model je opcion; bez znacke je bolje nego 500
        logger.warning("Model nije uspeo da oceni katalog za korisnika %s", user_id, exc_info=True)
        return {}

    if scores.shape[0] != ids.shape[0]:
        logger.warning(
            "Model je vratio %s ocena za katalog od %s recepata; znacka se preskace.",
            scores.shape[0],
            ids.shape[0],
        )
        return {}

    # Ista maska kao u preporukama: nekonacne ocene i vec ocenjeni recepti ne
    # smeju u prozor normalizacije, inace raspon postane beskonacan i round(nan)
    # puca. Sortiranjem padaju na kraj, pa dobijaju MATCH_TAIL ako se ipak traze.
    usable = np.isfinite(scores)
    if rated_ids:
        usable &= ~np.isin(ids, np.asarray(rated_ids, dtype=ids.dtype))
    scores[~usable] = -np.inf

    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]
    rank_of = {int(ids[index]): rank for rank, index in enumerate(order)}

    rated_set = {int(recipe_id) for recipe_id in rated_ids}
    wanted = [
        recipe_id
        for recipe_id in dict.fromkeys(int(value) for value in recipe_ids)
        if recipe_id in rank_of and recipe_id not in rated_set
    ]
    if not wanted:
        return {}

    percents = match_percent_from_scores(sorted_scores, [rank_of[rid] for rid in wanted])
    return dict(zip(wanted, percents, strict=True))


def similar_from_model(
    db: Session, *, recommender: Any, recipe_id: int, n: int
) -> list[dict] | None:
    """Slicni recepti preko modela; None znaci "koristi tag fallback".

    Koristi se iskljucivo `recommender.similar(...)`, jedina metoda koja vraca
    pravu kosinusnu slicnost nad ugradjenim vektorima recepata. Ranije se ovde
    rangiralo preko `score()` pa se objavljivala `match_percent / 100`: to je
    znacka iz opsega 60-99, dakle broj koji nikada ne pada ispod 0.6 i osmom
    rezultatu od 40.000 daje "0.80". Tag fallback ispod vraca udeo zajednickih
    tagova (0.2-1.0), pa su dve putanje objavljivale dve razlicite skale pod
    istim imenom.
    """
    if recommender is None:
        return None

    similar = getattr(recommender, "similar", None)
    if similar is None:
        logger.warning("Model nema metodu similar(); koristi se tag fallback.")
        return None

    try:
        pairs = list(similar(int(recipe_id), n))
    except Exception:  # model je opcion, greska znaci fallback
        logger.warning("Model nije uspeo da nadje slicne za recept %s", recipe_id, exc_info=True)
        return None

    neighbours: list[tuple[int, float]] = []
    for raw in pairs:
        parsed = _id_and_similarity(raw)
        if parsed is None or parsed[0] == recipe_id or not math.isfinite(parsed[1]):
            continue
        neighbours.append(parsed)

    by_id = {
        recipe.id: recipe for recipe in load_recipes_in_order(db, [rid for rid, _ in neighbours])
    }

    result = [
        {"recipe": to_card(by_id[rid]), "similarity": round(similarity, 4)}
        for rid, similarity in neighbours
        if rid in by_id
    ]

    # Prazna lista je isto razlog za fallback kao i None: katalog artefakta ume
    # da odluta ispred baze, pa svi susedi otpadnu. Bez ovoga bi ruter praznu
    # listu shvatio kao uspeh i tag fallback se nikada ne bi pokrenuo.
    return result or None


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


def _onboarding_top_up(
    db: Session, *, already: Sequence[int], catalog: set[int] | None, needed: int
) -> list[int]:
    """Dopuna onboarding liste najpopularnijim receptima.

    Prvo se uzimaju recepti koje model poznaje: ocena na receptu van kataloga
    ne pomera korisnika sa popularity fallback-a, pa mu onboarding ne bi vredeo.
    """
    seen = set(already)
    pool = [
        int(recipe_id)
        for recipe_id in db.scalars(
            select(Recipe.id).order_by(Recipe.popularity_rank).limit(ONBOARDING_POPULARITY_LIMIT)
        ).all()
    ]
    known = pool if catalog is None else [rid for rid in pool if rid in catalog]

    extra: list[int] = []
    for source in (known, pool):
        for recipe_id in source:
            if len(extra) >= needed:
                return extra
            if recipe_id not in seen:
                seen.add(recipe_id)
                extra.append(recipe_id)
    return extra


def build_onboarding_cards(db: Session, recommender: Any) -> list[dict]:
    """Recepti za onboarding: 2 po kategoriji, isprepletani.

    Kada je model ucitan, kandidati se suzavaju na katalog modela PRE nego sto
    se bazen presece na dve kartice. Ranije je SQL sekao na deset najpopularnijih
    po kategoriji pa se tek onda radio presek, tako da kategorija cijih je svih
    deset recepata van kataloga nije davala nijednu karticu.

    Lista nikada nema manje od `settings.onboarding_min_ratings` kartica: ispod
    toga nalog ne moze da zavrsi onboarding i guard ga trajno vraca sa /home.
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

    ids = _catalog_ids(recommender)
    catalog = set(ids.tolist()) if ids is not None else None
    if catalog is not None:
        pools = {tag: [i for i in pool if i in catalog] for tag, pool in pools.items()}

    chosen = {tag: pool[:ONBOARDING_PER_CATEGORY] for tag, pool in pools.items()}

    # Preplitanje: prvo po jedan iz svake kategorije, pa drugi krug.
    ordered_ids: list[int] = []
    for slot in range(ONBOARDING_PER_CATEGORY):
        for tag in ONBOARDING_CATEGORIES:
            pool = chosen[tag]
            if slot < len(pool):
                ordered_ids.append(pool[slot])

    minimum = settings.onboarding_min_ratings
    if len(ordered_ids) < minimum:
        ordered_ids += _onboarding_top_up(
            db, already=ordered_ids, catalog=catalog, needed=minimum - len(ordered_ids)
        )

    cards = [to_card(recipe) for recipe in load_recipes_in_order(db, ordered_ids)]

    # Upozorenje se racuna nad onim sto se STVARNO vraca. Ranije je stajalo pre
    # preseka sa katalogom, pa nikada nije prijavilo pravi manjak.
    returned = {card["id"] for card in cards}
    empty = [tag for tag in ONBOARDING_CATEGORIES if not returned.intersection(chosen[tag])]
    if empty:
        logger.warning("Onboarding kategorije bez ijedne kartice: %s", ", ".join(empty))

    if len(cards) < minimum:
        logger.error(
            "Onboarding vraca %d kartica, a za zavrsetak je potrebno %d - "
            "novi nalog nece moci da izadje sa onboarding ekrana.",
            len(cards),
            minimum,
        )

    return cards


def missing_onboarding_tags(db: Session, categories: Iterable[str] | None = None) -> list[str]:
    """Kategorije iz ONBOARDING_CATEGORIES kojih nema u tabeli `tags`."""
    wanted = list(categories or ONBOARDING_CATEGORIES)
    present = set(db.scalars(select(Tag.tag).where(Tag.tag.in_(wanted))).all())
    return [tag for tag in wanted if tag not in present]
