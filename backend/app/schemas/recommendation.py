"""Pydantic modeli za preporuke."""

from pydantic import BaseModel

from backend.app.schemas.recipe import RecipeCard


class Explanation(BaseModel):
    """'Zato sto ste ocenili X sa 5' - objasnjenje jedne preporuke."""

    because_recipe_id: int
    because_recipe_name: str
    because_rating: int
    similarity: float


class RecommendationItem(BaseModel):
    recipe: RecipeCard
    score: float
    # Znacka na kartici: 60-99 za rangirane kandidate, 55 za rep liste.
    match_percent: int
    explanation: Explanation | None


class RecommendationsResponse(BaseModel):
    # "mult_vae" kada je model ucitan i korisnik ima pozitivne ocene, inace "popularity".
    model: str
    total_candidates: int
    items: list[RecommendationItem]
