"""Ciste tekstualne pomocne funkcije (bez spoljnih zavisnosti).

normalize_ingredient se koristi i u ETL-u i kasnije za normalizaciju
korisnickog upita u pretrazi - zato mora da ostane deterministicna i
bez ikakvih zavisnosti van standardne biblioteke.
"""

import re

# ---------------------------------------------------------------- nazivi

_WHITESPACE_RE = re.compile(r"\s+")


def clean_name(raw: str | None) -> str:
    """Sazima uzastopne razmake i skida ivice. Prazan rezultat resava pozivalac."""
    if not raw:
        return ""
    return _WHITESPACE_RE.sub(" ", str(raw)).strip()


# ------------------------------------------------------------------ tagovi

# Strukturni tagovi iz Food.com dataseta koji na kartici recepta ne znace nista.
CARD_TAG_BLACKLIST: frozenset[str] = frozenset(
    {
        "time-to-make",
        "course",
        "main-ingredient",
        "preparation",
        "occasion",
        "equipment",
        "number-of-servings",
        "dietary",
        "cuisine",
        "taste-mood",
    }
)

# npr. "30-minutes-or-less", "4-hours-or-less"
_DURATION_TAG_RE = re.compile(r"^\d+-(minutes|hours)-or-less$")


def meaningful_tags(tags: list[str], limit: int | None = 4) -> list[str]:
    """Izdvaja tagove koji nose informaciju za prikaz na kartici recepta.

    `limit=None` vraca sve takve tagove - koristi ga stranica recepta, da bi
    prvi tag bio isti kao na kartici u mrezi.
    """
    result: list[str] = []
    seen: set[str] = set()

    for tag in tags or []:
        if not isinstance(tag, str):
            continue

        normalized = tag.strip().lower()
        if not normalized or normalized in seen:
            continue
        if normalized in CARD_TAG_BLACKLIST:
            continue
        if _DURATION_TAG_RE.match(normalized):
            continue

        seen.add(normalized)
        result.append(normalized)

        if limit is not None and len(result) >= limit:
            break

    return result


# -------------------------------------------------------------- sastojci

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Nepravilna mnozina koja se ne resava opstim pravilima.
# "tomatoes"/"potatoes" su namerno izbaceni - pokriva ih pravilo za -oes,
# isto kao i "mangoes", "avocadoes" i ostale koje spisak nikada nije imao.
_IRREGULAR_PLURALS: dict[str, str] = {
    "leaves": "leaf",
    "cookies": "cookie",
    "brownies": "brownie",
    "loaves": "loaf",
    "halves": "half",
    "knives": "knife",
    "chilies": "chili",
    "berries": "berry",
}

# Reci koje se zavrsavaju ovako nisu mnozina: asparagus, hummus, couscous.
_PROTECTED_SUFFIXES = ("ss", "us", "is")

# Reci koje nisu mnozina, a koje bi opsta pravila pogresno skratila.
# "molasses" bi preko pravila "es posle ss" postalo "molass".
_INVARIANT_WORDS: frozenset[str] = frozenset({"molasses"})


def _singularize(word: str) -> str:
    """Gruba singularizacija jedne reci - dovoljna za nazive sastojaka."""
    if word in _INVARIANT_WORDS:
        return word

    if word in _IRREGULAR_PLURALS:
        return _IRREGULAR_PLURALS[word]

    if len(word) <= 3:
        return word

    # berries -> berry (samo za duze reci, da "pies" ostane "pie" preko 's' pravila)
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"

    # mangoes -> mango, tomatoes -> tomato, echoes -> echo, buffaloes -> buffalo.
    # Bez ovog pravila "es" nize hvata samo ch/sh/x/ss, pa bi "mangoes" palo na
    # pravilo za golo 's' i zavrsilo kao "mangoe".
    # Kratke reci na -oes su skoro uvek mnozina osnove na -oe (shoes, aloes,
    # sloes, oboes) - njih namerno prepustamo pravilu za golo 's'.
    if word.endswith("oes") and len(word) >= 6:
        return word[:-2]

    # peaches -> peach, dishes -> dish, boxes -> box, glasses -> glass
    if word.endswith("es") and len(word) > 4:
        stem = word[:-2]
        if stem.endswith(("ch", "sh", "x", "ss")):
            return stem

    # eggs -> egg, ali NE asparagus/hummus/couscous/molasses
    if word.endswith("s") and not word.endswith(_PROTECTED_SUFFIXES):
        return word[:-1]

    return word


def normalize_ingredient(raw: str | None) -> tuple[str, list[str]]:
    """Normalizuje naziv sastojka.

    Mala slova, sve sto nije alfanumerik (ukljucujuci crticu) postaje razmak,
    zatim tokenizacija i singularizacija svakog tokena.

    Vraca (normalizovana_fraza, tokeni).
    """
    if not raw:
        return "", []

    lowered = str(raw).lower()
    spaced = _NON_ALNUM_RE.sub(" ", lowered)

    tokens = [_singularize(token) for token in spaced.split() if token]

    return " ".join(tokens), tokens
