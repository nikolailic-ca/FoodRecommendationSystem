from pathlib import Path
import pickle
import ast

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import get_current_user
from ..auth_database import get_connection


router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"]
)


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATASETS_DIR = PROJECT_ROOT / "datasets"
SAVED_MODELS_DIR = PROJECT_ROOT / "ai" / "saved_models"

RECIPES_FILE = DATASETS_DIR / "RAW_recipes.csv"
INTERACTIONS_FILE = DATASETS_DIR / "RAW_interactions.csv"

POPULARITY_MODEL_FILE = (
    SAVED_MODELS_DIR / "popularity_baseline.pkl"
)


# ============================================================
# LOAD DATA
# ============================================================

print("Loading recommendation system data...")

recipes_df = pd.read_csv(RECIPES_FILE)

interactions_df = pd.read_csv(
    INTERACTIONS_FILE
)

print(f"Loaded recipes: {len(recipes_df)}")
print(f"Loaded interactions: {len(interactions_df)}")


# ============================================================
# LOAD SAVED POPULARITY MODEL
# ============================================================

if not POPULARITY_MODEL_FILE.exists():
    raise FileNotFoundError(
        f"Popularity model not found: {POPULARITY_MODEL_FILE}"
    )


with open(POPULARITY_MODEL_FILE, "rb") as f:
    popularity_model = pickle.load(f)


recipe_popularity = popularity_model["recipe_popularity"]

print("Popularity model loaded successfully.")

print(
    f"Popularity model contains "
    f"{len(recipe_popularity)} recipes."
)


# ============================================================
# ONBOARDING RECIPES
# ============================================================

ONBOARDING_RECIPE_IDS = [
    401283,  # pizza
    54100,   # burger
    83873,   # chicken
    328976,  # carbonara
    297256,  # gyros
    250232,  # fries
    27995,   # spicy
    501408,  # pancakes
    221166,  # steak
    500166   # tacos
]


# ============================================================
# HELPER - USER RATED RECIPES
# ============================================================

def get_user_rated_recipe_ids(user_id: int):

    # Ratings from original dataset
    dataset_rated = set(
        interactions_df.loc[
            interactions_df["user_id"] == user_id,
            "recipe_id"
        ].tolist()
    )

    # Ratings from our application database
    connection = get_connection()

    try:

        database_ratings = connection.execute(
            """
            SELECT recipe_id
            FROM user_ratings
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchall()

    finally:
        connection.close()

    database_rated = {
        row["recipe_id"]
        for row in database_ratings
    }

    return dataset_rated | database_rated


# ============================================================
# HELPER - INGREDIENT MATCHING
# ============================================================

def recipe_contains_ingredients(
    ingredients_value,
    selected_ingredients
):
    """
    Returns True if the recipe contains ALL selected ingredients.
    """

    if not selected_ingredients:
        return True

    if pd.isna(ingredients_value):
        return False

    try:

        if isinstance(ingredients_value, str):
            parsed = ast.literal_eval(ingredients_value)
        else:
            parsed = ingredients_value

    except (ValueError, SyntaxError):
        parsed = [str(ingredients_value)]

    recipe_ingredients = " ".join(
        str(ingredient).lower()
        for ingredient in parsed
    )

    return all(
        ingredient.lower() in recipe_ingredients
        for ingredient in selected_ingredients
    )


# ============================================================
# RECOMMENDATIONS
# ============================================================

def generate_popular_recommendations(
    user_id: int,
    n: int = 10,
    name: str | None = None,
    max_minutes: int | None = None,
    ingredients: list[str] | None = None
):
    """
    Generate recommendations using the saved
    popularity baseline model.

    Recipes already rated by the user are excluded.

    Optional filters:
    - name
    - max_minutes
    - ingredients
    """

    # ========================================================
    # 1. USER RATED RECIPES
    # ========================================================

    user_rated = get_user_rated_recipe_ids(user_id)


    # ========================================================
    # 2. START WITH POPULARITY MODEL
    # ========================================================

    recommendations = recipe_popularity[
        ~recipe_popularity["recipe_id"].isin(user_rated)
    ].copy()


    # ========================================================
    # 3. ADD RECIPE INFORMATION
    # ========================================================

    recommendations = recommendations.merge(
        recipes_df[
            [
                "id",
                "name",
                "minutes",
                "nutrition",
                "n_steps",
                "description",
                "ingredients"
            ]
        ],
        left_on="recipe_id",
        right_on="id",
        how="left"
    )

    recommendations = recommendations.drop(
        columns=["id"],
        errors="ignore"
    )


    # ========================================================
    # 4. FILTER BY NAME
    # ========================================================

    if name:

        name = name.strip().lower()

        if name:

            recommendations = recommendations[
                recommendations["name"]
                .fillna("")
                .str.lower()
                .str.contains(
                    name,
                    na=False
                )
            ]


    # ========================================================
    # 5. FILTER BY MAXIMUM COOKING TIME
    # ========================================================

    if max_minutes is not None:

        recommendations = recommendations[
            pd.to_numeric(
                recommendations["minutes"],
                errors="coerce"
            ) <= max_minutes
        ]


    # ========================================================
    # 6. FILTER BY INGREDIENTS
    # ========================================================

    if ingredients:

        cleaned_ingredients = [
            ingredient.strip().lower()
            for ingredient in ingredients
            if ingredient.strip()
        ]

        if cleaned_ingredients:

            mask = recommendations["ingredients"].apply(
                lambda value:
                recipe_contains_ingredients(
                    value,
                    cleaned_ingredients
                )
            )

            recommendations = recommendations[mask]


    # ========================================================
    # 7. TAKE TOP N
    # ========================================================

    recommendations = recommendations.head(n).copy()


    # ========================================================
    # 8. CLEAN DATA
    # ========================================================

    recommendations = recommendations.fillna("")

    return recommendations


# ============================================================
# GET RECOMMENDATIONS FOR CURRENT USER
# ============================================================

@router.get("/me")
def get_my_recommendations(
    n: int = Query(
        default=10,
        ge=1,
        le=50
    ),

    name: str | None = Query(
        default=None
    ),

    max_minutes: int | None = Query(
        default=None,
        ge=1
    ),

    ingredients: str | None = Query(
        default=None
    ),

    current_user: dict = Depends(get_current_user)
):

    user_id = current_user["id"]


    # ========================================================
    # CONVERT INGREDIENT STRING TO LIST
    # ========================================================

    ingredient_list = None

    if ingredients:

        ingredient_list = [
            ingredient.strip()
            for ingredient in ingredients.split(",")
            if ingredient.strip()
        ]


    # ========================================================
    # GENERATE RECOMMENDATIONS
    # ========================================================

    recommendations = generate_popular_recommendations(
        user_id=user_id,
        n=n,
        name=name,
        max_minutes=max_minutes,
        ingredients=ingredient_list
    )


    return {
        "user_id": user_id,
        "model": "popularity_baseline",

        "filters": {
            "name": name,
            "max_minutes": max_minutes,
            "ingredients": ingredient_list or []
        },

        "count": len(recommendations),

        "recommendations": (
            recommendations
            .to_dict(orient="records")
        )
    }


# ============================================================
# INGREDIENT AUTOCOMPLETE
# ============================================================

# ============================================================
# PREPARE INGREDIENTS ON STARTUP
# ============================================================

all_ingredients = set()

for value in recipes_df["ingredients"].dropna():
    try:
        parsed = ast.literal_eval(value)

        for ingredient in parsed:
            ingredient = str(ingredient).strip().lower()

            if ingredient:
                all_ingredients.add(ingredient)

    except (ValueError, SyntaxError):
        continue

all_ingredients = sorted(all_ingredients)

print(f"Loaded unique ingredients: {len(all_ingredients)}")

@router.get("/ingredients")
def search_ingredients(
    query: str = Query(min_length=1),
    limit: int = Query(
        default=10,
        ge=1,
        le=20
    )
):
    query = query.strip().lower()

    if not query:
        return {
            "query": query,
            "ingredients": []
        }

    matches = [
        ingredient
        for ingredient in all_ingredients
        if query in ingredient
    ]

    matches = matches[:limit]

    return {
        "query": query,
        "count": len(matches),
        "ingredients": matches
    }


# ============================================================
# ONBOARDING
# ============================================================

@router.get("/onboarding")
def get_onboarding_recipes():

    onboarding_recipes = recipes_df[
        recipes_df["id"].isin(
            ONBOARDING_RECIPE_IDS
        )
    ].copy()


    # Preserve defined order
    onboarding_recipes["order"] = (
        onboarding_recipes["id"].apply(
            ONBOARDING_RECIPE_IDS.index
        )
    )


    onboarding_recipes = (
        onboarding_recipes
        .sort_values("order")
        .drop(columns=["order"])
        .fillna("")
    )


    return {
        "count": len(onboarding_recipes),
        "recipes": onboarding_recipes.to_dict(
            orient="records"
        )
    }