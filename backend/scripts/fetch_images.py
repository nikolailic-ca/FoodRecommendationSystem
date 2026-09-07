"""Fetches one Pexels photo per recipe, most popular first.

The Food.com dataset ships no images. Recipes without a photo fall back to a
generated tile in the UI, so this script is optional and safe to interrupt:
every recipe it has already attempted is recorded in `recipe_images`, and a
later run picks up where this one stopped.

Usage:
    uv run python -m backend.scripts.fetch_images --limit 300
    uv run python -m backend.scripts.fetch_images --retry-missing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import psycopg

from backend.app.core.config import settings
from backend.app.services.text import clean_name

API_URL = "https://api.pexels.com/v1/search"

# Pexels rejects the default urllib User-Agent with 403, so always send one.
USER_AGENT = "FoodRec/0.1 (bachelor thesis project)"

# Free tier: 200 requests/hour. 18.5s between calls keeps us just under it.
DEFAULT_DELAY = 18.5

# Words that describe the poster rather than the dish; they only add noise to
# an image search ("best ever chicken" finds nothing "best ever").
_FILLER = frozenset(
    {
        "recipe",
        "recipes",
        "best",
        "easy",
        "quick",
        "simple",
        "ever",
        "aka",
        "style",
        "homemade",
        "perfect",
        "favorite",
        "favourite",
        "amazing",
        "delicious",
        "ultimate",
        "real",
        "authentic",
        "classic",
        "original",
        "famous",
        "world",
        "s",
        "my",
        "our",
        "your",
        "the",
        "a",
        "an",
        "and",
        "or",
        "for",
        "with",
        "in",
        "on",
        "to",
        "of",
        "from",
        "that",
        "this",
        "it",
        "you",
        "die",
        "low",
        "fat",
        "free",
        "diabetic",
        "ww",
        "oamc",
        "rsc",
        "crock",
        "pot",
        "microwave",
        "kittencal",
        "is",
        "are",
        "was",
        "were",
        "there",
        "here",
        "yes",
        "no",
        "not",
        "all",
        "some",
        "any",
        "very",
        "great",
        "good",
        "super",
        "nice",
        "wonderful",
        "awesome",
    }
)

_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")
_ROMAN_RE = re.compile(r"^[ivxlcdm]+$")


def build_query(name: str, words: int = 4) -> str:
    """Turns a Food.com recipe name into something an image search can use."""
    text = _NON_ALNUM_RE.sub(" ", clean_name(name).lower())
    tokens = [
        t
        for t in text.split()
        if t and t not in _FILLER and not t.isdigit() and not _ROMAN_RE.match(t)
    ]
    return " ".join(tokens[:words])


@dataclass
class Photo:
    url: str
    source_url: str
    photographer: str
    photographer_url: str


class RateLimited(Exception):
    """Pexels answered 429; carries how long to wait."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limited, cekam {retry_after:.0f}s")
        self.retry_after = retry_after


def search_photo(query: str, api_key: str, timeout: float = 25.0) -> Photo | None:
    """One Pexels search. Returns None when the query has no landscape match."""
    url = f"{API_URL}?" + urllib.parse.urlencode(
        {"query": query, "per_page": 1, "orientation": "landscape"}
    )
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            reset = exc.headers.get("X-Ratelimit-Reset")
            wait = 60.0
            if reset and reset.isdigit():
                wait = max(5.0, float(reset) - time.time())
            raise RateLimited(min(wait, 3600.0)) from exc
        raise

    photos = payload.get("photos") or []
    if not photos:
        return None
    photo = photos[0]
    return Photo(
        url=photo["src"]["large"],
        source_url=photo.get("url", ""),
        photographer=photo.get("photographer", ""),
        photographer_url=photo.get("photographer_url", ""),
    )


def search_with_retries(
    query: str, api_key: str, attempts: int = 3, rate_limit_waits: int = 5
) -> Photo | None:
    """Retries transient failures; a rate limit is waited out, not counted.

    A 429 costs no retry: waiting is the correct response to it, and spending an
    attempt on it meant three rate limits in a row exhausted the budget without
    a single real error and the recipe was recorded as failed. `rate_limit_waits`
    only stops the loop from waiting forever.
    """
    attempt = 0
    waits = 0
    while True:
        try:
            return search_photo(query, api_key)
        except RateLimited as exc:
            waits += 1
            if waits > rate_limit_waits:
                raise
            print(f"    limit dostignut, pauza {exc.retry_after:.0f}s", flush=True)
            time.sleep(exc.retry_after)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            attempt += 1
            if attempt >= attempts:
                raise
            backoff = 2.0**attempt
            print(f"    greska ({exc}); ponovo za {backoff:.0f}s", flush=True)
            time.sleep(backoff)


def select_targets(
    conn: psycopg.Connection, limit: int, retry_missing: bool
) -> list[tuple[int, str]]:
    """Most popular recipes that have not been attempted yet."""
    if retry_missing:
        sql = """
            SELECT r.id, r.name
            FROM recipes r
            JOIN recipe_images i ON i.recipe_id = r.id
            WHERE i.url IS NULL
            ORDER BY r.popularity_rank
            LIMIT %s
        """
    else:
        sql = """
            SELECT r.id, r.name
            FROM recipes r
            LEFT JOIN recipe_images i ON i.recipe_id = r.id
            WHERE i.recipe_id IS NULL
            ORDER BY r.popularity_rank
            LIMIT %s
        """
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        return [(row[0], row[1]) for row in cur.fetchall()]


def store(conn: psycopg.Connection, recipe_id: int, photo: Photo | None) -> None:
    """Records the attempt. A NULL url means 'searched, found nothing'."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recipe_images
                (recipe_id, url, source, source_url, photographer, photographer_url, fetched_at)
            VALUES (%s, %s, 'pexels', %s, %s, %s, now())
            ON CONFLICT (recipe_id) DO UPDATE SET
                url = EXCLUDED.url,
                source = EXCLUDED.source,
                source_url = EXCLUDED.source_url,
                photographer = EXCLUDED.photographer,
                photographer_url = EXCLUDED.photographer_url,
                fetched_at = EXCLUDED.fetched_at
            """,
            (
                recipe_id,
                photo.url if photo else None,
                photo.source_url if photo else None,
                photo.photographer if photo else None,
                photo.photographer_url if photo else None,
            ),
        )
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.scripts.fetch_images",
        description="Preuzima fotografije sa Pexels-a za najpopularnije recepte.",
    )
    parser.add_argument("--limit", type=int, default=200, help="koliko recepata obraditi")
    parser.add_argument(
        "--retry-missing",
        action="store_true",
        help="ponovo pokusaj recepte kod kojih pretraga ranije nije nasla fotografiju",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"pauza izmedju poziva u sekundama (podrazumevano {DEFAULT_DELAY})",
    )
    args = parser.parse_args()

    api_key = settings.pexels_api_key.strip()
    if not api_key:
        print(
            "PEXELS_API_KEY nije podesen u .env.\n"
            "Napravi besplatan kljuc na https://www.pexels.com/api/ i upisi ga u .env.",
            file=sys.stderr,
        )
        return 1

    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    started = time.monotonic()
    found = missing = failed = 0

    with psycopg.connect(dsn) as conn:
        targets = select_targets(conn, args.limit, args.retry_missing)
        if not targets:
            print("Nema recepata za obradu. Sve je vec pokusano.")
            return 0

        total = len(targets)
        print(f"Obradjujem {total} recepata, pauza {args.delay:.1f}s izmedju poziva.")
        estimate = total * args.delay / 60.0
        print(f"Procenjeno trajanje: {estimate:.0f} min. Prekid je bezbedan, nastavak radi.\n")

        for index, (recipe_id, name) in enumerate(targets, start=1):
            # Pacing ide na POCETAK petlje, pre svakog poziva osim prvog. Kada je
            # pauza stajala na kraju, `continue` iz except grane ju je preskakao,
            # pa je skripta na gresku odgovarala tako sto je ubrzavala - i to bas
            # kada je Pexels pod pritiskom.
            if index > 1:
                time.sleep(args.delay)

            query = build_query(name)
            if not query:
                query = "food"

            try:
                photo = search_with_retries(query, api_key)
                if photo is None:
                    # Second chance with a broader query. To je JOS jedan poziv,
                    # pa mora da potrosi svoj slot: bez ove pauze recept bez
                    # pogotka salje dva zahteva u jednom intervalu i besplatni
                    # limit od 200 na sat se probija.
                    time.sleep(args.delay)
                    fallback = " ".join(query.split()[:2]) + " food"
                    photo = search_with_retries(fallback, api_key)
            except Exception as exc:  # noqa: BLE001 - one bad recipe must not stop the run
                failed += 1
                print(f"[{index}/{total}] {name[:48]!r} -> GRESKA: {exc}", flush=True)
                continue

            store(conn, recipe_id, photo)
            if photo:
                found += 1
                print(f"[{index}/{total}] {query!r} -> {photo.photographer}", flush=True)
            else:
                missing += 1
                print(f"[{index}/{total}] {query!r} -> nema pogodaka", flush=True)

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM recipe_images WHERE url IS NOT NULL")
            total_with_photo = cur.fetchone()[0]

    elapsed = time.monotonic() - started
    print("\n" + "=" * 52)
    print(f"  nadjeno              {found:>10,}")
    print(f"  bez pogotka          {missing:>10,}")
    print(f"  greske               {failed:>10,}")
    print(f"  ukupno sa fotkom     {total_with_photo:>10,}")
    print(f"  trajanje             {elapsed / 60:>9.1f} min")
    print("=" * 52)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
