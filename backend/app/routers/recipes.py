from fastapi import APIRouter, HTTPException, Query

from ..database import recipes_df


router = APIRouter(
    prefix="/recipes",
    tags=["Recipes"]
)


@router.get("/")
def get_recipes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    data = recipes_df.iloc[offset:offset + limit]

    return {
        "total": len(recipes_df),
        "limit": limit,
        "offset": offset,
        "recipes": data.fillna("").to_dict(orient="records")
    }


@router.get("/search")
def search_recipes(
    query: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100)
):
    mask = (
        recipes_df["name"]
        .fillna("")
        .str.contains(query, case=False, na=False)
    )

    results = recipes_df[mask].head(limit)

    return {
        "query": query,
        "count": len(results),
        "recipes": results.fillna("").to_dict(orient="records")
    }


@router.get("/{recipe_id}")
def get_recipe(recipe_id: int):

    result = recipes_df[recipes_df["id"] == recipe_id]

    if result.empty:
        raise HTTPException(
            status_code=404,
            detail="Recipe not found"
        )

    return result.iloc[0].fillna("").to_dict()