import { client } from './client'
import type {
  RatingEntry,
  RatingMutationResult,
  RecipeCard,
  User,
} from './types'

/** `GET /users/me` */
export async function getMe(): Promise<User> {
  const { data } = await client.get<User>('/users/me')

  return data
}

/** `GET /users/me/ratings?min_rating=` */
export async function getMyRatings(minRating?: number): Promise<RatingEntry[]> {
  const { data } = await client.get<RatingEntry[]>('/users/me/ratings', {
    params: minRating === undefined ? undefined : { min_rating: minRating },
  })

  return data
}

/** `PUT /users/me/ratings/{recipe_id}` — creates or replaces one rating. */
export async function rateRecipe(
  recipeId: number,
  rating: number,
): Promise<RatingMutationResult> {
  const { data } = await client.put<RatingMutationResult>(
    `/users/me/ratings/${recipeId}`,
    { rating },
  )

  return data
}

/** `DELETE /users/me/ratings/{recipe_id}` */
export async function deleteRating(recipeId: number): Promise<void> {
  await client.delete(`/users/me/ratings/${recipeId}`)
}

/** `GET /users/me/favorites` */
export async function getFavorites(): Promise<RecipeCard[]> {
  const { data } = await client.get<RecipeCard[]>('/users/me/favorites')

  return data
}

/** `PUT /users/me/favorites/{recipe_id}` */
export async function addFavorite(recipeId: number): Promise<void> {
  await client.put(`/users/me/favorites/${recipeId}`)
}

/** `DELETE /users/me/favorites/{recipe_id}` */
export async function removeFavorite(recipeId: number): Promise<void> {
  await client.delete(`/users/me/favorites/${recipeId}`)
}
