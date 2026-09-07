import { client } from './client'
import type {
  RecipeCard,
  RecommendationParams,
  RecommendationResponse,
} from './types'

/**
 * `GET /recommendations/me?n=&offset=&name=&max_minutes=&ingredients=&tags=`
 *
 * Falls back to the popularity model server-side when the user has not rated
 * enough recipes yet; the answer says which model produced it.
 */
export async function getRecommendations(
  params: RecommendationParams = {},
): Promise<RecommendationResponse> {
  const { data } = await client.get<RecommendationResponse>(
    '/recommendations/me',
    { params },
  )

  return data
}

/** `GET /recommendations/onboarding` — the recipes shown during onboarding. */
export async function getOnboardingRecipes(): Promise<RecipeCard[]> {
  const { data } = await client.get<RecipeCard[]>('/recommendations/onboarding')

  return data
}
