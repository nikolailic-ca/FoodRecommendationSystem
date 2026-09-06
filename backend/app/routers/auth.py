from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from jose import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import hashlib

from ..auth_database import get_connection

import sqlite3

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


SECRET_KEY = "food-recommendation-system-secret-key"
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


class RatingRequest(BaseModel):
    recipe_id: int
    rating: int


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    ratings: list[RatingRequest] = []


@router.post("/register")
def register_user(data: RegisterRequest):

    username = data.username.strip()
    email = data.email.strip().lower()
    password = data.password

    # =========================
    # VALIDATION
    # =========================

    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must contain at least 3 characters"
        )

    if len(password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 6 characters"
        )

    if len(data.ratings) < 5:
        raise HTTPException(
            status_code=400,
            detail="You must rate at least 5 recipes"
        )

    for rating in data.ratings:

        if rating.rating < 1 or rating.rating > 5:
            raise HTTPException(
                status_code=400,
                detail="Rating must be between 1 and 5"
            )

    # Provera da se isti recept nije ocenio dva puta
    recipe_ids = [
        rating.recipe_id
        for rating in data.ratings
    ]

    if len(recipe_ids) != len(set(recipe_ids)):
        raise HTTPException(
            status_code=400,
            detail="You cannot rate the same recipe twice"
        )

    # =========================
    # PASSWORD HASH
    # =========================

    password_hash = hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()

    connection = get_connection()

    try:

        # =========================
        # CREATE USER
        # =========================

        cursor = connection.execute(
            """
            INSERT INTO users (
                username,
                email,
                password_hash
            )
            VALUES (?, ?, ?)
            """,
            (
                username,
                email,
                password_hash
            )
        )

        user_id = cursor.lastrowid

        # =========================
        # SAVE INITIAL RATINGS
        # =========================

        for rating in data.ratings:

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
                    rating.recipe_id,
                    rating.rating
                )
            )

        connection.commit()

        # =========================
        # RETURN USER
        # =========================

        user = connection.execute(
            """
            SELECT id, username, email, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        return {
            "message": "User registered successfully",
            "user": dict(user),
            "ratings_saved": len(data.ratings)
        }

    except sqlite3.IntegrityError as e:

        connection.rollback()

        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=400,
                detail="Username or email already exists"
            )

        raise

    finally:
        connection.close()


@router.post("/login")
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    username = form_data.username.strip()
    password = form_data.password

    password_hash = hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()

    connection = get_connection()

    try:

        user = connection.execute(
            """
            SELECT id, username, email, password_hash
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

    finally:
        connection.close()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if user["password_hash"] != password_hash:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = jwt.encode(
        {
            "sub": str(user["id"]),
            "username": user["username"]
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    connection = get_connection()

    try:

        user = connection.execute(
            """
            SELECT id, username, email, created_at
            FROM users
            WHERE id = ?
            """,
            (int(user_id),)
        ).fetchone()

    finally:
        connection.close()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return dict(user)