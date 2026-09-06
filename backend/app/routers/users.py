from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..database import interactions_df
from ..auth_database import get_connection
from ..database import interactions_df, recipes_df

from .auth import get_current_user
import pandas as pd

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


# =========================================================
# REQUEST MODELS
# =========================================================

class RatingRequest(BaseModel):
    recipe_id: int
    rating: int


# =========================================================
# CURRENT USER
# =========================================================

@router.get("/me")
def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    return current_user


# =========================================================
# SAVE / UPDATE CURRENT USER RATING
# =========================================================

@router.post("/me/ratings")
def save_rating(
    data: RatingRequest,
    current_user: dict = Depends(get_current_user)
):

    user_id = current_user["id"]

    # Provera ocene
    if data.rating < 1 or data.rating > 5:
        raise HTTPException(
            status_code=400,
            detail="Rating must be between 1 and 5"
        )

    connection = get_connection()

    try:

        # Proveravamo da li je korisnik već ocenio recept
        existing_rating = connection.execute(
            """
            SELECT id
            FROM user_ratings
            WHERE user_id = ?
              AND recipe_id = ?
            """,
            (
                user_id,
                data.recipe_id
            )
        ).fetchone()

        if existing_rating:
            raise HTTPException(
                status_code=400,
                detail="You have already rated this recipe"
            )

        else:

            # Ako nije -> dodajemo novu ocenu
            connection.execute(
                """
                INSERT INTO user_ratings (
                    user_id,
                    recipe_id,
                    rating
                )
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    data.recipe_id,
                    data.rating
                )
            )

            message = "Rating saved successfully"

        connection.commit()

        return {
            "message": message,
            "user_id": user_id,
            "recipe_id": data.recipe_id,
            "rating": data.rating
        }

    finally:
        connection.close()


# =========================================================
# GET CURRENT USER RATINGS
# =========================================================

@router.get("/me/ratings")
def get_my_ratings(
    current_user: dict = Depends(get_current_user)
):

    user_id = current_user["id"]

    connection = get_connection()

    try:

        ratings = connection.execute(
            """
            SELECT
                recipe_id,
                rating,
                created_at
            FROM user_ratings
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        ).fetchall()

        return {
            "user_id": user_id,
            "ratings": [dict(rating) for rating in ratings]
        }

    finally:
        connection.close()


# =========================================================
# OLD DATASET USER ENDPOINTS
# =========================================================

@router.get("/{user_id}")
def get_user(user_id: int):

    user_interactions = interactions_df[
        interactions_df["user_id"] == user_id
    ]

    if user_interactions.empty:
        raise HTTPException(
            status_code=404,
            detail=f"User {user_id} not found in interactions dataset"
        )

    return {
        "user_id": user_id,
        "ratings_count": len(user_interactions)
    }


@router.get("/{user_id}/ratings")
def get_user_ratings(user_id: int):

    user_interactions = interactions_df[
        interactions_df["user_id"] == user_id
    ]

    if user_interactions.empty:
        raise HTTPException(
            status_code=404,
            detail=f"User {user_id} not found in interactions dataset"
        )

    return {
        "user_id": user_id,
        "ratings": user_interactions.fillna("").to_dict(
            orient="records"
        )
    }


@router.get("/")
def get_users(limit: int = 20):

    user_ids = (
        interactions_df["user_id"]
        .dropna()
        .drop_duplicates()
        .head(limit)
        .tolist()
    )

    return {
        "users": user_ids
    }

@router.get("/me/ratings")
def get_my_ratings(
    current_user: dict = Depends(get_current_user)
):

    user_id = current_user["id"]

    connection = get_connection()

    try:

        ratings = connection.execute(
            """
            SELECT
                recipe_id,
                rating,
                created_at
            FROM user_ratings
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,)
        ).fetchall()

    finally:
        connection.close()

    ratings_list = []

    for rating in ratings:

        recipe_id = rating["recipe_id"]

        recipe = recipes_df[
            recipes_df["id"] == recipe_id
        ]

        recipe_data = {
            "recipe_id": recipe_id,
            "rating": rating["rating"],
            "created_at": rating["created_at"],
            "name": "",
            "minutes": "",
            "description": ""
        }

        if not recipe.empty:

            recipe_row = recipe.iloc[0]

            recipe_data["name"] = (
                "" if pd.isna(recipe_row["name"])
                else recipe_row["name"]
            )

            recipe_data["minutes"] = (
                "" if pd.isna(recipe_row["minutes"])
                else recipe_row["minutes"]
            )

            recipe_data["description"] = (
                "" if pd.isna(recipe_row["description"])
                else recipe_row["description"]
            )

        ratings_list.append(recipe_data)

    return {
        "user_id": user_id,
        "ratings": ratings_list
    }