"""ETL: Food.com CSV -> PostgreSQL.

Pokretanje iz korena projekta:

    uv run python -m backend.scripts.etl
    uv run python -m backend.scripts.etl --limit 1000
    uv run python -m backend.scripts.etl --recipes putanja.csv --interactions putanja.csv

Skripta je idempotentna: recepti se upsertuju (ON CONFLICT DO UPDATE), pa se
ponovnim pokretanjem NE brisu korisnicke ocene i omiljeni recepti.
"""

from __future__ import annotations

import argparse
import ast
import csv
import math
import sys
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from backend.app.core.config import PROJECT_ROOT, settings
from backend.app.services.text import clean_name, normalize_ingredient

# Neki review-ovi u datasetu su ogromni - podizemo limit polja.
csv.field_size_limit(10**8)

DEFAULT_RECIPES = PROJECT_ROOT / "datasets" / "RAW_recipes.csv"
DEFAULT_INTERACTIONS = PROJECT_ROOT / "datasets" / "RAW_interactions.csv"

PROGRESS_EVERY = 200_000
RECIPE_BATCH = 20_000

# Kolone staging tabele - redosled mora da prati INSERT ... SELECT nize.
RECIPE_COLUMNS = (
    "id",
    "name",
    "minutes",
    "contributor_id",
    "submitted",
    "description",
    "n_steps",
    "n_ingredients",
    "steps",
    "ingredients",
    "tags",
    "calories",
    "total_fat_pdv",
    "sugar_pdv",
    "sodium_pdv",
    "protein_pdv",
    "saturated_fat_pdv",
    "carbohydrates_pdv",
    "rating_count",
    "avg_rating",
    "popularity_rank",
)


class EtlError(Exception):
    """Greska koja se korisniku prikazuje bez stack trace-a."""


# --------------------------------------------------------------- pomocne


def _require_csv(path: Path, kind: str) -> None:
    if not path.exists():
        raise EtlError(
            f"Nije pronadjen {kind} fajl:\n"
            f"    {path}\n\n"
            "Dataset nije u repozitorijumu (prevelik je za git). Preuzmite ga sa Kaggle-a:\n"
            '    "Food.com Recipes and Interactions"\n'
            "    https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions\n\n"
            f"Raspakujte RAW_recipes.csv i RAW_interactions.csv u folder:\n"
            f"    {PROJECT_ROOT / 'datasets'}\n"
            "ili prosledite putanje rucno preko --recipes i --interactions."
        )


def _dsn_from_settings() -> str:
    """psycopg3 ocekuje cist postgresql:// DSN, bez SQLAlchemy '+psycopg' sufiksa."""
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _to_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    # NaN/inf ne mogu u double precision kolonu na smislen nacin
    if not math.isfinite(result):
        return None
    return result


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _parse_list(value: str | None) -> tuple[list, bool]:
    """ast.literal_eval nad kolonom koja je Python lista upisana kao string.

    Vraca (lista, da_li_je_pukao_parse).
    """
    if value is None or value == "":
        return [], False
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return [], True

    if isinstance(parsed, list):
        return parsed, False
    if isinstance(parsed, tuple):
        return list(parsed), False
    return [], True


# ------------------------------------------------------------- pass 1


def aggregate_interactions(path: Path, limit: int | None = None) -> dict[int, tuple[int, float]]:
    """Prolaz 1: po receptu skuplja broj ocena i zbir ocena.

    Ocene sa rating = 0 znace "recenzija bez ocene" i NE ulaze u agregat.
    """
    print(f"[1/2] Citanje interakcija: {path}")
    totals: dict[int, list[float]] = {}

    read = 0
    counted = 0
    skipped_zero = 0

    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            read += 1

            recipe_id = _to_int(row.get("recipe_id"))
            rating = _to_float(row.get("rating"))

            if recipe_id is not None and rating is not None:
                if rating > 0:
                    entry = totals.get(recipe_id)
                    if entry is None:
                        totals[recipe_id] = [1, rating]
                    else:
                        entry[0] += 1
                        entry[1] += rating
                    counted += 1
                else:
                    skipped_zero += 1

            if read % PROGRESS_EVERY == 0:
                print(f"      ...{read:,} interakcija")

            if limit is not None and read >= limit:
                break

    print(
        f"      gotovo: {read:,} redova, {counted:,} ocena u agregatu, "
        f"{skipped_zero:,} sa rating=0 preskoceno, {len(totals):,} recepata sa ocenom"
    )
    return {rid: (int(cnt), total) for rid, (cnt, total) in totals.items()}


# ------------------------------------------------------------- pass 2


def read_recipes(
    path: Path,
    ratings: dict[int, tuple[int, float]],
    limit: int | None = None,
) -> tuple[list[dict], int]:
    """Prolaz 2: parsira recepte i spaja ih sa agregatima ocena."""
    print(f"[2/2] Citanje recepata: {path}")

    recipes: list[dict] = []
    eval_failures = 0
    read = 0

    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            read += 1

            recipe_id = _to_int(row.get("id"))
            if recipe_id is None:
                continue

            steps, f1 = _parse_list(row.get("steps"))
            ingredients, f2 = _parse_list(row.get("ingredients"))
            tags, f3 = _parse_list(row.get("tags"))
            nutrition, f4 = _parse_list(row.get("nutrition"))
            eval_failures += f1 + f2 + f3 + f4

            name = clean_name(row.get("name"))
            if not name:
                name = f"recipe {recipe_id}"

            description = clean_name(row.get("description")) or None

            # nutrition: [calories, total_fat, sugar, sodium, protein, sat_fat, carbs]
            nutrition_values: list[float | None] = [
                _to_float(nutrition[i]) if i < len(nutrition) else None for i in range(7)
            ]

            count, total = ratings.get(recipe_id, (0, 0.0))
            avg_rating = round(total / count, 4) if count else None

            recipes.append(
                {
                    "id": recipe_id,
                    "name": name,
                    "minutes": _to_int(row.get("minutes")),
                    "contributor_id": _to_int(row.get("contributor_id")),
                    "submitted": _to_date(row.get("submitted")),
                    "description": description,
                    "n_steps": _to_int(row.get("n_steps")),
                    "n_ingredients": _to_int(row.get("n_ingredients")),
                    "steps": [str(s) for s in steps],
                    "ingredients": [str(i) for i in ingredients],
                    "tags": [str(t) for t in tags],
                    "nutrition": nutrition_values,
                    "rating_count": count,
                    "avg_rating": avg_rating,
                }
            )

            if read % 50_000 == 0:
                print(f"      ...{read:,} recepata")

            if limit is not None and read >= limit:
                break

    print(f"      gotovo: {len(recipes):,} recepata, {eval_failures:,} neuspelih literal_eval")
    return recipes, eval_failures


def assign_popularity_rank(recipes: list[dict]) -> None:
    """Rangira recepte: prvo po broju ocena, pa po proseku, pa po id-u. Rank krece od 1."""
    order = sorted(
        range(len(recipes)),
        key=lambda i: (
            -recipes[i]["rating_count"],
            -(recipes[i]["avg_rating"] or 0.0),
            recipes[i]["id"],
        ),
    )
    for rank, index in enumerate(order, start=1):
        recipes[index]["popularity_rank"] = rank


# ------------------------------------------------------------- upis


def _recipe_row(recipe: dict) -> tuple:
    nutrition = recipe["nutrition"]
    return (
        recipe["id"],
        recipe["name"],
        recipe["minutes"],
        recipe["contributor_id"],
        recipe["submitted"],
        recipe["description"],
        recipe["n_steps"],
        recipe["n_ingredients"],
        Jsonb(recipe["steps"]),
        Jsonb(recipe["ingredients"]),
        Jsonb(recipe["tags"]),
        *nutrition,
        recipe["rating_count"],
        recipe["avg_rating"],
        recipe["popularity_rank"],
    )


def load_recipes(conn: psycopg.Connection, recipes: list[dict]) -> None:
    """COPY u UNLOGGED staging tabelu, pa upsert u recipes.

    Namerno se NE koristi TRUNCATE recipes CASCADE - to bi obrisalo
    user_ratings i user_favorites.
    """
    print(f"      upis {len(recipes):,} recepata (staging + upsert)...")

    columns_sql = ", ".join(RECIPE_COLUMNS)
    updatable = [c for c in RECIPE_COLUMNS if c != "id"]
    update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in updatable)

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS recipes_staging")
        cur.execute(
            "CREATE UNLOGGED TABLE recipes_staging "
            "(LIKE recipes INCLUDING DEFAULTS EXCLUDING CONSTRAINTS EXCLUDING INDEXES)"
        )

        with cur.copy(f"COPY recipes_staging ({columns_sql}) FROM STDIN") as copy:
            for recipe in recipes:
                copy.write_row(_recipe_row(recipe))

        cur.execute(
            f"INSERT INTO recipes ({columns_sql}) "
            f"SELECT {columns_sql} FROM recipes_staging "
            f"ON CONFLICT (id) DO UPDATE SET {update_sql}"
        )
        inserted = cur.rowcount

        cur.execute("DROP TABLE recipes_staging")

    print(f"      upsert-ovano {inserted:,} redova u recipes")


def _ingredient_rows(batch: list[dict]) -> Iterator[tuple]:
    for recipe in batch:
        for position, raw in enumerate(recipe["ingredients"]):
            norm, tokens = normalize_ingredient(raw)
            yield (recipe["id"], position, raw, norm or None, tokens or None)


def _tag_rows(batch: list[dict]) -> Iterator[tuple]:
    for recipe in batch:
        seen: set[str] = set()
        for raw in recipe["tags"]:
            tag = str(raw).strip().lower()
            if tag and tag not in seen:
                seen.add(tag)
                yield (recipe["id"], tag)


def load_side_tables(conn: psycopg.Connection, recipes: list[dict]) -> None:
    """Puni recipe_ingredients / recipe_tags, pa iz njih gradi ingredients / tags."""
    print("      upis sporednih tabela (sastojci i tagovi)...")

    with conn.cursor() as cur:
        # Ove tabele su potpuno izvedene iz dataseta - bezbedno je obrisati ih.
        cur.execute("TRUNCATE recipe_ingredients, recipe_tags, ingredients, tags")

        for start in range(0, len(recipes), RECIPE_BATCH):
            batch = recipes[start : start + RECIPE_BATCH]

            with cur.copy(
                "COPY recipe_ingredients "
                "(recipe_id, position, ingredient, ingredient_norm, tokens) FROM STDIN"
            ) as copy:
                for row in _ingredient_rows(batch):
                    copy.write_row(row)

            with cur.copy("COPY recipe_tags (recipe_id, tag) FROM STDIN") as copy:
                for row in _tag_rows(batch):
                    copy.write_row(row)

            print(f"      ...{min(start + RECIPE_BATCH, len(recipes)):,}/{len(recipes):,} recepata")

        cur.execute(
            "INSERT INTO ingredients (name, display_name, recipe_count) "
            "SELECT ingredient_norm, min(ingredient), count(DISTINCT recipe_id) "
            "FROM recipe_ingredients "
            "WHERE ingredient_norm IS NOT NULL AND ingredient_norm <> '' "
            "GROUP BY ingredient_norm"
        )
        cur.execute(
            "INSERT INTO tags (tag, recipe_count) "
            "SELECT tag, count(DISTINCT recipe_id) FROM recipe_tags GROUP BY tag"
        )


def print_summary(conn: psycopg.Connection, eval_failures: int, elapsed: float) -> None:
    tables = (
        "recipes",
        "recipe_ingredients",
        "ingredients",
        "recipe_tags",
        "tags",
        "users",
        "user_ratings",
        "user_favorites",
        "recipe_images",
    )

    print("\n" + "=" * 52)
    print("ETL ZAVRSEN")
    print("=" * 52)

    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f"SELECT count(*) FROM {table}")
            print(f"  {table:<20} {cur.fetchone()[0]:>12,}")

    print("-" * 52)
    print(f"  {'literal_eval greske':<20} {eval_failures:>12,}")
    print(f"  {'trajanje':<20} {elapsed:>11.1f}s")
    print("=" * 52)


# ------------------------------------------------------------- main


def run(recipes_path: Path, interactions_path: Path, limit: int | None) -> int:
    started = time.perf_counter()

    _require_csv(recipes_path, "RAW_recipes.csv")
    _require_csv(interactions_path, "RAW_interactions.csv")

    ratings = aggregate_interactions(interactions_path)
    recipes, eval_failures = read_recipes(recipes_path, ratings, limit=limit)

    if not recipes:
        raise EtlError("Nijedan recept nije procitan - proverite ulazni CSV fajl.")

    assign_popularity_rank(recipes)

    with psycopg.connect(_dsn_from_settings()) as conn:
        with conn.cursor() as cur:
            # Sigurnosna provera: nikada ne pisati u tudju bazu.
            cur.execute("SELECT current_database()")
            current_db = cur.fetchone()[0]
            if current_db != "foodrec":
                raise EtlError(f"Povezani smo na bazu {current_db!r}, a ocekuje se 'foodrec'.")

            cur.execute("SET synchronous_commit = off")

        load_recipes(conn, recipes)
        load_side_tables(conn, recipes)
        conn.commit()

        with conn.cursor() as cur:
            print("      ANALYZE...")
            cur.execute("ANALYZE")

        print_summary(conn, eval_failures, time.perf_counter() - started)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.scripts.etl",
        description="Ucitava Food.com CSV dataset u PostgreSQL bazu.",
    )
    parser.add_argument(
        "--recipes", type=Path, default=DEFAULT_RECIPES, help="putanja do RAW_recipes.csv"
    )
    parser.add_argument(
        "--interactions",
        type=Path,
        default=DEFAULT_INTERACTIONS,
        help="putanja do RAW_interactions.csv",
    )
    parser.add_argument("--limit", type=int, default=None, help="ucitaj samo prvih N recepata")
    args = parser.parse_args(argv)

    try:
        return run(args.recipes, args.interactions, args.limit)
    except EtlError as exc:
        print(f"\nGRESKA: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
