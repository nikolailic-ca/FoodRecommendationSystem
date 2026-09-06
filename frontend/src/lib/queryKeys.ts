import type { RecipeSearchParams } from '@/api/types'

import type { RecommendationFilters } from './filters'

/**
 * Every query key in the app, in one place.
 *
 * The prefixes matter: invalidating `['ratings']` also invalidates
 * `['ratings', 4]`, and invalidating `['recommendations']` reaches every
 * filtered variant of the grid.
 */
export const queryKeys = {
  me: () => ['me'] as const,

  ratings: (minRating?: number) =>
    (minRating === undefined
      ? ['ratings']
      : ['ratings', minRating]) as readonly unknown[],

  favorites: () => ['favorites'] as const,

  recipe: (recipeId: number) => ['recipe', recipeId] as const,

  // Kept out of the `['recipe', id]` prefix so rating a recipe does not force a
  // refetch of its "similar recipes" strip.
  similar: (recipeId: number, n: number) => ['similar', recipeId, n] as const,

  recipeSearch: (params: RecipeSearchParams) => ['recipes', params] as const,

  recommendations: (filters: RecommendationFilters) =>
    ['recommendations', filters] as const,

  onboardingRecipes: () => ['onboarding-recipes'] as const,

  suggestions: (kind: 'ingredients' | 'tags', query: string) =>
    ['suggestions', kind, query] as const,
} as const

/** Prefixes used for invalidation, kept next to the keys they belong to. */
export const queryKeyRoots = {
  me: ['me'] as const,
  ratings: ['ratings'] as const,
  favorites: ['favorites'] as const,
  recommendations: ['recommendations'] as const,
} as const
