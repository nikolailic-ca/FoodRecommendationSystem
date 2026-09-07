import { client } from './client'
import type { RecipeDetail, SimilarRecipe } from './types'

/** `GET /recipes/{id}` */
export async function getRecipe(recipeId: number): Promise<RecipeDetail> {
  const { data } = await client.get<RecipeDetail>(`/recipes/${recipeId}`)

  return data
}

/** `GET /recipes/{id}/similar?n=` */
export async function getSimilarRecipes(
  recipeId: number,
  n = 8,
): Promise<SimilarRecipe[]> {
  const { data } = await client.get<SimilarRecipe[]>(
    `/recipes/${recipeId}/similar`,
    { params: { n } },
  )

  return data
}

/** `GET /ingredients?query=&limit=` */
export async function getIngredients(
  query: string,
  limit = 10,
): Promise<string[]> {
  const { data } = await client.get<string[]>('/ingredients', {
    params: { query, limit },
  })

  return data
}

/** `GET /tags?query=&limit=` */
export async function getTags(query: string, limit = 20): Promise<string[]> {
  const { data } = await client.get<string[]>('/tags', {
    params: { query, limit },
  })

  return data
}
