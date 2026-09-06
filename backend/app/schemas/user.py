"""Pydantic modeli za korisnika, ocene i omiljene recepte."""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.schemas.recipe import RecipeCard


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime
    ratings_count: int
    # True kada korisnik ima bar ONBOARDING_MIN_RATINGS ocena.
    onboarding_completed: bool


class RatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)


class RatingOut(BaseModel):
    recipe_id: int
    rating: int
    created_at: datetime
    updated_at: datetime


class UserRatingItem(BaseModel):
    """Ocena zajedno sa karticom recepta (za stranicu 'moje ocene')."""

    recipe: RecipeCard
    rating: int
    created_at: datetime
    updated_at: datetime
