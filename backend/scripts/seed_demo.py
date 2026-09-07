"""DEMO podaci za razvoj - 40 izmisljenih recepata.

NIJE deo dataseta i NIJE za produkciju. Sluzi samo da se API moze isprobati
dok Kaggle dataset (RAW_recipes.csv) nije preuzet: pokriva sve filtere,
svih 15 onboarding kategorija, paginaciju i slucaj slike koja ne postoji.

Pokretanje iz korena projekta:

    uv run python -m backend.scripts.seed_demo            # ubaci / osvezi
    uv run python -m backend.scripts.seed_demo --clear    # ukloni demo recepte

Skripta je idempotentna. Demo recepti koriste id-jeve od 9_000_001 navise,
sto je van opsega Food.com id-jeva, pa se ne mogu sudariti sa pravim ETL-om.
Popularity rank im je 1..40, pa POSLE pravog ETL-a treba pokrenuti --clear.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.db.models import Recipe, RecipeImage, RecipeIngredient, RecipeTag
from backend.app.db.session import SessionLocal, verify_database
from backend.app.services.text import normalize_ingredient

DEMO_ID_BASE = 9_000_000

# Tagovi koje dobija svaki recept - namerno ukljucuju i strukturne tagove iz
# dataseta, da bi se videlo da ih meaningful_tags izbacuje sa kartice.
COMMON_TAGS = ("course", "preparation", "main-ingredient", "time-to-make")

# (naziv, minuti, kategorija, dodatni tagovi, sastojci, koraci, opis)
DEMO_RECIPES: tuple[tuple, ...] = (
    (
        "grilled lemon herb chicken",
        35,
        "chicken",
        ("easy", "grilling", "healthy"),
        ("chicken breasts", "lemons", "olive oil", "garlic cloves", "fresh rosemary"),
        6,
        (
            "A bright, summery grilled chicken that marinates in lemon juice, olive oil and "
            "rosemary for half an hour and then goes straight onto a very hot grill."
        ),
    ),
    (
        "honey garlic chicken thighs",
        45,
        "chicken",
        ("weeknight", "comfort-food"),
        ("chicken thighs", "honey", "garlic cloves", "soy sauce", "butter"),
        7,
        "Sticky, glossy chicken thighs braised in a honey and garlic pan sauce.",
    ),
    (
        "classic beef stroganoff",
        50,
        "beef",
        ("comfort-food", "one-pot"),
        ("beef sirloin", "mushrooms", "onions", "sour cream", "butter", "egg noodles"),
        8,
        (
            "The old fashioned version with seared strips of sirloin, a mustard and sour cream "
            "sauce and a heap of buttered egg noodles underneath."
        ),
    ),
    (
        "slow braised beef short ribs",
        240,
        "beef",
        ("make-ahead", "comfort-food"),
        ("beef short ribs", "red wine", "carrots", "onions", "tomato paste", "beef stock"),
        9,
        "Four hours in a low oven turns short ribs into something you can eat with a spoon.",
    ),
    (
        "maple glazed pork chops",
        30,
        "pork",
        ("weeknight", "30-minutes-or-less"),
        ("pork chops", "maple syrup", "dijon mustard", "butter", "fresh thyme"),
        5,
        "Thick cut chops seared hard and finished in a maple and mustard glaze.",
    ),
    (
        "pulled pork sandwiches",
        420,
        "pork",
        ("make-ahead", "crowd-pleaser"),
        ("pork shoulder", "brown sugar", "smoked paprika", "cider vinegar", "hamburger buns"),
        10,
        "Seven hours of very low heat, then two forks. Serve with slaw and plenty of napkins.",
    ),
    (
        "garlic butter shrimp scampi",
        20,
        "seafood",
        ("quick", "30-minutes-or-less"),
        ("shrimp", "garlic cloves", "butter", "white wine", "fresh parsley", "linguine"),
        5,
        "Twenty minutes from cold pan to dinner, and most of that is boiling the pasta water.",
    ),
    (
        "pan seared salmon with dill",
        25,
        "seafood",
        ("healthy", "30-minutes-or-less"),
        ("salmon fillets", "fresh dill", "lemons", "olive oil", "capers"),
        4,
        "Crisp skin, barely cooked centre, and a spoonful of dill and caper butter on top.",
    ),
    (
        "roasted eggplant parmesan",
        75,
        "vegetarian",
        ("comfort-food", "baked"),
        ("eggplant", "mozzarella cheese", "parmesan cheese", "tomato sauce", "eggs", "basil"),
        11,
        (
            "Roasting the eggplant instead of frying it keeps this lighter than the classic and "
            "means you are not standing over a pan of hot oil for half an hour."
        ),
    ),
    (
        "chickpea and spinach curry",
        35,
        "vegetarian",
        ("healthy", "one-pot", "vegan"),
        ("chickpeas", "spinach", "coconut milk", "curry powder", "onions", "garlic cloves"),
        6,
        "A pantry curry - one pan, one can of chickpeas, and a bag of spinach wilted in at the end.",
    ),
    (
        "spaghetti aglio e olio",
        20,
        "pasta",
        ("quick", "vegetarian-friendly"),
        ("spaghetti", "garlic cloves", "olive oil", "red pepper flakes", "fresh parsley"),
        4,
        "Five ingredients, one pan, and the only technique that matters is not burning the garlic.",
    ),
    (
        "baked ziti with ricotta",
        70,
        "pasta",
        ("comfort-food", "baked", "make-ahead"),
        ("ziti", "ricotta cheese", "mozzarella cheese", "tomato sauce", "eggs", "basil"),
        9,
        "The casserole that feeds eight people and reheats better than it bakes the first time.",
    ),
    (
        "chocolate fudge brownies",
        55,
        "desserts",
        ("baking", "chocolate"),
        ("dark chocolate", "butter", "eggs", "granulated sugar", "all-purpose flour", "cocoa"),
        7,
        "Dense, fudgy squares with a paper thin crackly top. Underbake them by two minutes.",
    ),
    (
        "lemon meringue pie",
        120,
        "desserts",
        ("baking", "citrus"),
        ("egg whites", "egg yolks", "lemons", "granulated sugar", "cornstarch", "pie crust"),
        14,
        "Sharp lemon curd under a cloud of meringue that has been whipped to stiff peaks.",
    ),
    (
        "hearty vegetable minestrone",
        60,
        "soups-stews",
        ("healthy", "one-pot", "vegan"),
        ("carrots", "celery", "cannellini beans", "tomatoes", "zucchini", "small pasta"),
        8,
        "Whatever is in the drawer, plus beans and a parmesan rind if you have one.",
    ),
    (
        "creamy potato leek soup",
        45,
        "soups-stews",
        ("comfort-food", "blender"),
        ("potatoes", "leeks", "heavy cream", "butter", "vegetable stock"),
        6,
        "Blended smooth, finished with cream, and better on the second day.",
    ),
    (
        "classic caesar salad",
        25,
        "salads",
        ("30-minutes-or-less", "no-cook"),
        ("romaine lettuce", "eggs", "anchovy fillets", "parmesan cheese", "croutons", "lemons"),
        5,
        "A real caesar dressing, coddled egg and anchovies included, whisked in the bowl.",
    ),
    (
        "watermelon feta salad",
        15,
        "salads",
        ("no-cook", "summer", "30-minutes-or-less"),
        ("watermelon", "feta cheese", "fresh mint", "olive oil", "lime juice"),
        3,
        "Salty, sweet and cold. Nothing to cook and nothing to think about.",
    ),
    (
        "fluffy buttermilk pancakes",
        30,
        "breakfast",
        ("30-minutes-or-less", "kid-friendly"),
        ("all-purpose flour", "buttermilk", "eggs", "butter", "baking powder", "granulated sugar"),
        6,
        "Let the batter rest ten minutes and do not stir out the lumps.",
    ),
    (
        "spinach and egg white omelette",
        15,
        "breakfast",
        ("healthy", "high-protein"),
        ("egg whites", "spinach", "feta cheese", "olive oil", "black pepper"),
        4,
        "A weekday omelette that is basically all protein and greens.",
    ),
    (
        "quick garlic fried rice",
        18,
        "30-minutes-or-less",
        ("leftovers", "one-pot"),
        ("cooked rice", "garlic cloves", "eggs", "scallions", "soy sauce", "sesame oil"),
        5,
        "Day old rice, a very hot wok, and more garlic than seems sensible.",
    ),
    (
        "five minute avocado toast",
        5,
        "30-minutes-or-less",
        ("no-cook", "vegetarian-friendly"),
        ("avocados", "sourdough bread", "lemon juice", "chili flakes", "sea salt"),
        3,
        "Barely a recipe, but the ratio of lemon to salt is the whole point.",
    ),
    (
        "margherita pizza",
        90,
        "pizza",
        ("baking", "vegetarian-friendly"),
        ("bread flour", "mozzarella cheese", "san marzano tomatoes", "fresh basil", "olive oil"),
        10,
        "Hot oven, thin base, three toppings. The dough needs an hour but the bake takes eight minutes.",
    ),
    (
        "pepperoni pan pizza",
        110,
        "pizza",
        ("baking", "comfort-food"),
        ("bread flour", "pepperoni", "mozzarella cheese", "tomato sauce", "olive oil"),
        11,
        "Thick, oily bottomed pan pizza with the cheese pushed right to the edge.",
    ),
    (
        "chicken enchiladas verdes",
        65,
        "mexican",
        ("baked", "crowd-pleaser"),
        ("chicken breasts", "corn tortillas", "tomatillos", "monterey jack cheese", "sour cream"),
        9,
        "Poached chicken rolled into tortillas and drowned in a bright green tomatillo sauce.",
    ),
    (
        "black bean tacos",
        25,
        "mexican",
        ("vegan", "30-minutes-or-less"),
        ("black beans", "corn tortillas", "red onions", "limes", "fresh cilantro", "avocados"),
        5,
        "The weeknight taco: a can of beans, a hot pan, and whatever is left in the fridge.",
    ),
    (
        "thai green curry",
        40,
        "asian",
        ("one-pot", "spicy"),
        ("green curry paste", "coconut milk", "chicken thighs", "thai basil", "fish sauce"),
        7,
        "Fry the paste until it splits before anything else goes in - that is the whole trick.",
    ),
    (
        "beef and broccoli stir fry",
        28,
        "asian",
        ("30-minutes-or-less", "weeknight"),
        ("flank steak", "broccoli", "soy sauce", "garlic cloves", "fresh ginger", "cornstarch"),
        6,
        "Velveted beef, blistered broccoli, and a sauce that thickens in the last thirty seconds.",
    ),
    (
        "risotto alla milanese",
        50,
        "italian",
        ("comfort-food", "vegetarian-friendly"),
        ("arborio rice", "saffron threads", "parmesan cheese", "butter", "white wine", "onions"),
        8,
        "Stand at the stove for twenty minutes and stir. There is no shortcut worth taking.",
    ),
    (
        "tiramisu",
        180,
        "italian",
        ("make-ahead", "no-bake"),
        ("mascarpone cheese", "eggs", "espresso", "ladyfingers", "granulated sugar", "cocoa"),
        8,
        "Assembled in twenty minutes, then it needs a full night in the fridge to set properly.",
    ),
    (
        "eggplant caponata",
        55,
        "vegetarian",
        ("make-ahead", "vegan", "sicilian"),
        ("eggplant", "celery", "green olives", "capers", "red wine vinegar", "tomatoes"),
        7,
        "Sweet and sour Sicilian eggplant that is better cold, the day after you make it.",
    ),
    (
        "moroccan lamb tagine",
        150,
        "soups-stews",
        ("make-ahead", "spicy"),
        ("lamb shoulder", "dried apricots", "chickpeas", "ras el hanout", "onions", "almonds"),
        10,
        "Slow, sweet and heavily spiced. Serve over couscous with a spoonful of the sauce.",
    ),
    (
        "buttermilk fried chicken",
        95,
        "chicken",
        ("comfort-food", "fried"),
        ("chicken pieces", "buttermilk", "all-purpose flour", "paprika", "peanut oil"),
        9,
        "An overnight buttermilk brine, a seasoned flour dredge, and oil held at exactly 165 degrees.",
    ),
    (
        "greek village salad",
        12,
        "salads",
        ("no-cook", "healthy", "30-minutes-or-less"),
        ("tomatoes", "cucumbers", "red onions", "feta cheese", "kalamata olives", "olive oil"),
        3,
        "No lettuce anywhere near it. Just good tomatoes, a slab of feta and plenty of oregano.",
    ),
    (
        "banana bread",
        75,
        "desserts",
        ("baking", "kid-friendly"),
        ("ripe bananas", "all-purpose flour", "eggs", "butter", "brown sugar", "baking soda"),
        7,
        "The blacker the bananas the better the loaf.",
    ),
    (
        "shakshuka",
        35,
        "breakfast",
        ("one-pot", "vegetarian-friendly"),
        ("eggs", "tomatoes", "red bell peppers", "onions", "cumin", "harissa"),
        6,
        "Eggs poached directly in a spiced tomato and pepper sauce, eaten out of the pan with bread.",
    ),
    (
        "mushroom risotto",
        55,
        "italian",
        ("comfort-food", "vegetarian-friendly"),
        ("arborio rice", "mushrooms", "parmesan cheese", "butter", "vegetable stock", "shallots"),
        9,
        "Dried porcini in the stock is what makes this taste like more mushrooms than it contains.",
    ),
    (
        "beef chili con carne",
        130,
        "beef",
        ("one-pot", "make-ahead", "spicy"),
        ("ground beef", "kidney beans", "tomatoes", "chili powder", "onions", "dark chocolate"),
        8,
        "Two hours at a bare simmer and a square of dark chocolate stirred in at the end.",
    ),
    (
        "vegetable pad thai",
        30,
        "asian",
        ("30-minutes-or-less", "vegetarian-friendly"),
        ("rice noodles", "eggs", "tamarind paste", "bean sprouts", "peanuts", "scallions"),
        6,
        "Have everything chopped before the wok goes on - the cooking itself takes four minutes.",
    ),
    (
        "blueberry cheesecake",
        300,
        "desserts",
        ("baking", "make-ahead"),
        ("cream cheese", "eggs", "graham crackers", "blueberries", "granulated sugar", "butter"),
        12,
        "Baked in a water bath so the top does not crack, then chilled for at least four hours.",
    ),
)


def _nutrition(index: int, minutes: int) -> dict:
    """Deterministicne ali raznovrsne nutritivne vrednosti (demo podaci)."""
    base = 120 + (index * 37) % 640
    return {
        "calories": float(base),
        "total_fat_pdv": float((index * 11) % 60 + 4),
        "sugar_pdv": float((index * 17) % 90 + 2),
        "sodium_pdv": float((index * 23) % 70 + 3),
        "protein_pdv": float((index * 13) % 80 + 5),
        "saturated_fat_pdv": float((index * 7) % 50 + 2),
        "carbohydrates_pdv": float((minutes % 40) + 5),
    }


def _image_for(recipe_id: int, index: int) -> dict | None:
    """Svaki treci recept ima sliku, svaki treci ima red sa url = NULL.

    Svi redovi imaju iste kljuceve - visevrednosni INSERT to zahteva.
    """
    remainder = index % 3
    if remainder == 2:
        # Nema reda uopste: Pexels pretraga jos nije ni pokusana.
        return None
    if remainder == 1:
        # Pretraga je obavljena, fotografija nije nadjena - url ostaje NULL.
        return {
            "recipe_id": recipe_id,
            "url": None,
            "source": "demo",
            "source_url": None,
            "photographer": None,
            "photographer_url": None,
        }
    return {
        "recipe_id": recipe_id,
        "url": f"https://images.example.com/demo/{recipe_id}.jpg",
        "source": "demo",
        "source_url": f"https://www.pexels.com/photo/demo-{recipe_id}/",
        "photographer": "Demo Photographer",
        "photographer_url": "https://www.pexels.com/@demo",
    }


def _build_rows() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    recipes: list[dict] = []
    ingredients: list[dict] = []
    tags: list[dict] = []
    images: list[dict] = []

    for index, entry in enumerate(DEMO_RECIPES):
        name, minutes, category, extra_tags, ingredient_list, n_steps, description = entry
        recipe_id = DEMO_ID_BASE + index + 1

        all_tags = [category, *extra_tags, *COMMON_TAGS]
        steps = [f"Demo korak {step} za '{name}'." for step in range(1, n_steps + 1)]

        recipes.append(
            {
                "id": recipe_id,
                "name": name,
                "minutes": minutes,
                "contributor_id": 1,
                "submitted": date(2008, 1, 1).replace(day=(index % 28) + 1),
                "description": description,
                "n_steps": len(steps),
                "n_ingredients": len(ingredient_list),
                "steps": steps,
                "ingredients": list(ingredient_list),
                "tags": all_tags,
                # Popularnost opada sa rednim brojem - rank je gust, od 1.
                "rating_count": max(1, 500 - index * 11),
                "avg_rating": round(4.9 - (index % 20) * 0.07, 2),
                "popularity_rank": index + 1,
                **_nutrition(index, minutes),
            }
        )

        for position, raw in enumerate(ingredient_list):
            norm, tokens = normalize_ingredient(raw)
            ingredients.append(
                {
                    "recipe_id": recipe_id,
                    "position": position,
                    "ingredient": raw,
                    "ingredient_norm": norm or None,
                    "tokens": tokens or None,
                }
            )

        seen: set[str] = set()
        for tag in all_tags:
            if tag not in seen:
                seen.add(tag)
                tags.append({"recipe_id": recipe_id, "tag": tag})

        image = _image_for(recipe_id, index)
        if image is not None:
            images.append(image)

    return recipes, ingredients, tags, images


def _rebuild_aggregates(db) -> None:
    """ingredients i tags su potpuno izvedene tabele - kao u ETL-u."""
    db.execute(text("TRUNCATE ingredients, tags"))
    db.execute(
        text(
            "INSERT INTO ingredients (name, display_name, recipe_count) "
            "SELECT ingredient_norm, min(ingredient), count(DISTINCT recipe_id) "
            "FROM recipe_ingredients "
            "WHERE ingredient_norm IS NOT NULL AND ingredient_norm <> '' "
            "GROUP BY ingredient_norm"
        )
    )
    db.execute(
        text(
            "INSERT INTO tags (tag, recipe_count) "
            "SELECT tag, count(DISTINCT recipe_id) FROM recipe_tags GROUP BY tag"
        )
    )


def clear() -> int:
    """Brise samo demo recepte (kaskadno i njihove ocene/omiljene)."""
    with SessionLocal() as db:
        removed = db.execute(delete(Recipe).where(Recipe.id > DEMO_ID_BASE)).rowcount
        _rebuild_aggregates(db)
        db.commit()

    print(f"Uklonjeno demo recepata: {removed}")
    return 0


def seed() -> int:
    recipes, ingredients, tags, images = _build_rows()
    demo_ids = [row["id"] for row in recipes]

    with SessionLocal() as db:
        existing = db.scalar(select(Recipe.id).where(Recipe.id <= DEMO_ID_BASE).limit(1))
        if existing is not None:
            print(
                "UPOZORENJE: baza vec sadrzi prave recepte iz dataseta. "
                "Demo recepti koriste popularity_rank 1..40 i pokvarice redosled - "
                "pokrenite --clear kada zavrsite sa demo podacima.",
                file=sys.stderr,
            )

        insert_recipes = pg_insert(Recipe).values(recipes)
        updatable = [key for key in recipes[0] if key != "id"]
        db.execute(
            insert_recipes.on_conflict_do_update(
                index_elements=["id"],
                set_={key: insert_recipes.excluded[key] for key in updatable},
            )
        )

        # Sporedne tabele se za demo id-jeve uvek pisu iz nule.
        db.execute(delete(RecipeIngredient).where(RecipeIngredient.recipe_id.in_(demo_ids)))
        db.execute(delete(RecipeTag).where(RecipeTag.recipe_id.in_(demo_ids)))
        db.execute(delete(RecipeImage).where(RecipeImage.recipe_id.in_(demo_ids)))

        db.execute(pg_insert(RecipeIngredient).values(ingredients))
        db.execute(pg_insert(RecipeTag).values(tags))
        if images:
            db.execute(pg_insert(RecipeImage).values(images))

        _rebuild_aggregates(db)
        db.commit()

    print(
        f"Upisano: {len(recipes)} recepata, {len(ingredients)} sastojaka, "
        f"{len(tags)} tagova, {len(images)} slika."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.scripts.seed_demo",
        description="Ubacuje DEMO recepte za razvoj (nije dataset).",
    )
    parser.add_argument("--clear", action="store_true", help="ukloni demo recepte")
    args = parser.parse_args(argv)

    verify_database()
    return clear() if args.clear else seed()


if __name__ == "__main__":
    raise SystemExit(main())
