/**
 * Wire types for the FoodRec backend.
 *
 * These mirror the FastAPI response models one-to-one; nothing here is derived
 * or reshaped, so a mismatch with the backend shows up as a type error rather
 * than as a runtime surprise.
 */

/**
 * Nullability mirrors `backend/app/schemas/recipe.py` exactly: the Food.com
 * export leaves plenty of columns empty, so everything the ETL cannot
 * guarantee arrives as `null` and has to be rendered as such.
 */
export interface RecipeCard {
  id: number
  name: string
  minutes: number | null
  n_ingredients: number | null
  n_steps: number | null
  calories: number | null
  rating_count: number
  avg_rating: number | null
  image_url: string | null
  tags: string[]
  description_short: string
}

export interface Nutrition {
  calories: number | null
  total_fat_pdv: number | null
  sugar_pdv: number | null
  sodium_pdv: number | null
  protein_pdv: number | null
  saturated_fat_pdv: number | null
  carbohydrates_pdv: number | null
}

export interface RecipeImage {
  url: string
  photographer: string | null
  photographer_url: string | null
  source_url: string | null
}

export interface RecipeDetail extends RecipeCard {
  description: string | null
  steps: string[]
  ingredients: string[]
  nutrition: Nutrition
  submitted: string | null
  image: RecipeImage | null
  user_rating: number | null
  is_favorite: boolean
}

export interface User {
  id: number
  username: string
  email: string
  created_at: string
  ratings_count: number
  onboarding_completed: boolean
}

/* -------------------------------------------------------------------------- */
/* Auth                                                                       */
/* -------------------------------------------------------------------------- */

export interface AuthToken {
  access_token: string
  token_type: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
}

export interface RegisterResponse extends AuthToken {
  user: User
}

/* -------------------------------------------------------------------------- */
/* Ratings and favorites                                                      */
/* -------------------------------------------------------------------------- */

export interface RatingEntry {
  recipe: RecipeCard
  rating: number
  created_at: string
  updated_at: string
}

export interface RatingMutationResult {
  recipe_id: number
  rating: number
  created_at: string
  updated_at: string
}

/* -------------------------------------------------------------------------- */
/* Catalog                                                                    */
/* -------------------------------------------------------------------------- */

export interface RecipeSearchParams {
  query?: string
  limit?: number
  offset?: number
}

export interface RecipeSearchResult {
  total: number
  items: RecipeCard[]
}

export interface SimilarRecipe {
  recipe: RecipeCard
  similarity: number
}

/* -------------------------------------------------------------------------- */
/* Recommendations                                                            */
/* -------------------------------------------------------------------------- */

export type RecommendationModel = 'mult_vae' | 'popularity'

export interface RecommendationExplanation {
  because_recipe_id: number
  because_recipe_name: string
  because_rating: number
  similarity: number
}

export interface RecommendationItem {
  recipe: RecipeCard
  score: number
  match_percent: number
  explanation: RecommendationExplanation | null
}

export interface RecommendationResponse {
  model: RecommendationModel
  total_candidates: number
  items: RecommendationItem[]
}

/** Query string of `GET /recommendations/me`. */
export interface RecommendationParams {
  n?: number
  offset?: number
  name?: string
  max_minutes?: number
  /** Comma separated list, e.g. `chicken,garlic`. */
  ingredients?: string
  /** Comma separated list, e.g. `weeknight,one-pot`. */
  tags?: string
}

/* -------------------------------------------------------------------------- */
/* Errors                                                                     */
/* -------------------------------------------------------------------------- */

/** One entry of FastAPI's 422 `detail` array. */
export interface ValidationErrorItem {
  loc: (string | number)[]
  msg: string
  type: string
}

/** Body of every non-2xx FastAPI response. */
export interface ApiErrorBody {
  detail?: string | ValidationErrorItem[]
}
