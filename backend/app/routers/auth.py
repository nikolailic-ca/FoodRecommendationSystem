"""Registracija i prijava."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.api.deps import DbSession
from backend.app.core.security import (
    create_access_token,
    credentials_error,
    hash_password,
    verify_password,
)
from backend.app.db.models import User
from backend.app.schemas.auth import RegisterRequest, RegisterResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# Hes bez ijedne odgovarajuce lozinke. Sluzi da provera traje isto i kada
# korisnik ne postoji, pa se iz vremena odgovora ne moze zakljuciti
# koja korisnicka imena su zauzeta.
_DUMMY_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO1jHxvVYYVGYPQ0RtQhb5ZSbC7VBTfjK"


def _duplicate_field(error: IntegrityError) -> str:
    """Iz Postgres greske izvlaci koje je ogranicenje prekrseno."""
    constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "") or ""
    return "email" if "email" in constraint.lower() else "username"


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registracija korisnika",
)
def register(payload: RegisterRequest, db: DbSession) -> dict:
    """Kreira korisnika i odmah vraca token.

    Token je potreban jer frontend odmah posle registracije salje onboarding
    ocene - bez njega bi morao da radi jos jednu prijavu.
    """
    user = User(
        username=payload.username,
        # Email se u bazi uvek cuva malim slovima.
        email=str(payload.email).strip().lower(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        field = _duplicate_field(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "That email is already registered."
                if field == "email"
                else "That username is already taken."
            ),
        ) from exc

    db.refresh(user)

    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at,
            "ratings_count": 0,
            "onboarding_completed": False,
        },
    }


@router.post("/login", response_model=TokenResponse, summary="Prijava (OAuth2 form)")
def login(
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> dict:
    username = form_data.username.strip()
    user = db.scalar(select(User).where(User.username == username))

    password_hash = user.password_hash if user is not None else _DUMMY_HASH
    if not verify_password(form_data.password, password_hash) or user is None:
        raise credentials_error("Incorrect username or password.")

    return {"access_token": create_access_token(user.id), "token_type": "bearer"}
