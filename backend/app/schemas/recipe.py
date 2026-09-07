"""Pydantic modeli za recepte - tacno onaj oblik koji frontend ocekuje."""

from datetime import date

from pydantic import BaseModel


class RecipeCard(BaseModel):
    """Kratak prikaz recepta (lista, preporuke, omiljeni)."""

    id: int
    name: str
    minutes: int | None
    n_ingredients: int | None
    n_steps: int | None
    calories: float | None
    rating_count: int
    avg_rating: float | None
    image_url: str | None
    # Najvise 4 taga, bez strukturnih (vidi services/text.meaningful_tags).
    tags: list[str]
    description_short: str


class Nutrition(BaseModel):
    calories: float | None
    total_fat_pdv: float | None
    sugar_pdv: float | None
    sodium_pdv: float | None
    protein_pdv: float | None
    saturated_fat_pdv: float | None
    carbohydrates_pdv: float | None


class RecipeImageOut(BaseModel):
    url: str
    photographer: str | None
    photographer_url: str | None
    source_url: str | None


class RecipeDetail(RecipeCard):
    """Kartica + sve sto se prikazuje na stranici recepta."""

    description: str | None
    steps: list[str]
    ingredients: list[str]
    # Svi smisleni tagovi, ne samo cetiri sa kartice. Filter je isti kao na
    # kartici (bez strukturnih i tagova trajanja), pa je prvi tag isti na oba
    # mesta i frontend bira istu placeholder ikonicu.
    tags: list[str]
    nutrition: Nutrition
    submitted: date | None
    image: RecipeImageOut | None
    user_rating: int | None
    is_favorite: bool


class RecipeListResponse(BaseModel):
    total: int
    items: list[RecipeCard]


class SimilarRecipe(BaseModel):
    recipe: RecipeCard
    similarity: float
    # Koliko se recept poklapa sa ukusom PRIJAVLJENOG korisnika, isti opseg i
    # ista normalizacija kao na pocetnoj strani. `similarity` je nesto drugo:
    # blizina receptu koji se trenutno gleda. None znaci da znacke nema -
    # anoniman zahtev, model nije ucitan, ili je korisnik recept vec ocenio.
    match_percent: int | None = None
