import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { getErrorMessage } from '@/api/client'
import type { RecipeDetail } from '@/api/types'
import { deleteRating, getMyRatings, rateRecipe } from '@/api/users'
import { queryKeys, queryKeyRoots } from '@/lib/queryKeys'

/** Everything the user has rated, optionally only at or above `minRating`. */
export function useRatings(minRating?: number) {
  return useQuery({
    queryKey: queryKeys.ratings(minRating),
    queryFn: () => getMyRatings(minRating),
  })
}

interface RatingContext {
  previous: RecipeDetail | undefined
}

/**
 * Refreshes everything a rating touches.
 *
 * `['recommendations']` is marked stale but deliberately not refetched: the
 * grid the user is looking at would otherwise reorder under the cursor the
 * moment a star is clicked. It reloads on the next natural mount instead.
 */
function useRatingInvalidation() {
  const queryClient = useQueryClient()

  return (recipeId: number) => {
    void queryClient.invalidateQueries({ queryKey: queryKeyRoots.ratings })
    void queryClient.invalidateQueries({ queryKey: queryKeyRoots.me })
    void queryClient.invalidateQueries({ queryKey: queryKeys.recipe(recipeId) })
    void queryClient.invalidateQueries({
      queryKey: queryKeyRoots.recommendations,
      refetchType: 'none',
    })
  }
}

export interface RateRecipeVariables {
  recipeId: number
  rating: number
}

/** `PUT /users/me/ratings/{id}`, applied to the open recipe straight away. */
export function useRateRecipe() {
  const queryClient = useQueryClient()
  const invalidate = useRatingInvalidation()

  return useMutation({
    mutationFn: ({ recipeId, rating }: RateRecipeVariables) =>
      rateRecipe(recipeId, rating),

    onMutate: async ({ recipeId, rating }): Promise<RatingContext> => {
      const key = queryKeys.recipe(recipeId)
      await queryClient.cancelQueries({ queryKey: key })

      const previous = queryClient.getQueryData<RecipeDetail>(key)

      if (previous) {
        queryClient.setQueryData<RecipeDetail>(key, {
          ...previous,
          user_rating: rating,
        })
      }

      return { previous }
    },

    onError: (error, { recipeId }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.recipe(recipeId), context.previous)
      }

      toast.error(getErrorMessage(error, 'Could not save your rating.'))
    },

    onSettled: (_data, _error, { recipeId }) => {
      invalidate(recipeId)
    },
  })
}

/** `DELETE /users/me/ratings/{id}`. */
export function useDeleteRating() {
  const queryClient = useQueryClient()
  const invalidate = useRatingInvalidation()

  return useMutation({
    mutationFn: (recipeId: number) => deleteRating(recipeId),

    onMutate: async (recipeId): Promise<RatingContext> => {
      const key = queryKeys.recipe(recipeId)
      await queryClient.cancelQueries({ queryKey: key })

      const previous = queryClient.getQueryData<RecipeDetail>(key)

      if (previous) {
        queryClient.setQueryData<RecipeDetail>(key, {
          ...previous,
          user_rating: null,
        })
      }

      return { previous }
    },

    onError: (error, recipeId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.recipe(recipeId), context.previous)
      }

      toast.error(getErrorMessage(error, 'Could not remove your rating.'))
    },

    onSettled: (_data, _error, recipeId) => {
      invalidate(recipeId)
    },
  })
}
