from pathlib import Path
import pandas as pd


# Root projekta:
# FoodRecommendationSystem/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASETS_DIR = PROJECT_ROOT / "datasets"

RECIPES_FILE = DATASETS_DIR / "RAW_recipes.csv"
INTERACTIONS_FILE = DATASETS_DIR / "RAW_interactions.csv"


print("Project root:", PROJECT_ROOT)
print("Recipes file:", RECIPES_FILE)
print("Interactions file:", INTERACTIONS_FILE)


recipes_df = pd.read_csv(RECIPES_FILE)
interactions_df = pd.read_csv(INTERACTIONS_FILE)


print(f"Loaded recipes: {len(recipes_df)}")
print(f"Loaded interactions: {len(interactions_df)}")