import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { getErrorMessage } from '@/api/client'
import type { RecipeCard, RecipeDetail } from '@/api/types'
import { addFavorite, getFavorites, removeFavorite } from '@/api/users'
import { queryKeys, queryKeyRoots } from '@/lib/queryKeys'

/** The user's saved recipes. */
export function useFavorites() {
  return useQuery({
    queryKey: queryKeys.favorites(),
    queryFn: getFavorites,
  })
}

function toIdSet(recipes: RecipeCard[]): Set<number> {
  return new Set(recipes.map((recipe) => recipe.id))
}

/**
 * The same data as `useFavorites`, as a `Set` of ids — what a grid of cards
 * needs to decide whether each bookmark is filled.
 */
export function useFavoriteIds() {
  return useQuery({
    queryKey: queryKeys.favorites(),
    queryFn: getFavorites,
    select: toIdSet,
  })
}

export interface ToggleFavoriteVariables {
  recipe: RecipeCard
  /** Whether the recipe is a favourite *right now*. */
  isFavorite: boolean
}

interface ToggleFavoriteContext {
  previousFavorites: RecipeCard[] | undefined
  previousRecipe: RecipeDetail | undefined
}

/**
 * Flips the bookmark immediately, both in the favourites list and on the open
 * recipe, and rolls both back if the request fails.
 */
export function useToggleFavorite() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ recipe, isFavorite }: ToggleFavoriteVariables) =>
      isFavorite ? removeFavorite(recipe.id) : addFavorite(recipe.id),

    onMutate: async ({
      recipe,
      isFavorite,
    }): Promise<ToggleFavoriteContext> => {
      const favoritesKey = queryKeys.favorites()
      const recipeKey = queryKeys.recipe(recipe.id)

      await Promise.all([
        queryClient.cancelQueries({ queryKey: favoritesKey }),
        queryClient.cancelQueries({ queryKey: recipeKey }),
      ])

      const previousFavorites =
        queryClient.getQueryData<RecipeCard[]>(favoritesKey)
      const previousRecipe = queryClient.getQueryData<RecipeDetail>(recipeKey)

      if (previousFavorites) {
        queryClient.setQueryData<RecipeCard[]>(
          favoritesKey,
          isFavorite
            ? previousFavorites.filter((item) => item.id !== recipe.id)
            : [recipe, ...previousFavorites],
        )
      }

      if (previousRecipe) {
        queryClient.setQueryData<RecipeDetail>(recipeKey, {
          ...previousRecipe,
          is_favorite: !isFavorite,
        })
      }

      return { previousFavorites, previousRecipe }
    },

    onError: (error, { recipe }, context) => {
      if (context?.previousFavorites) {
        queryClient.setQueryData(
          queryKeys.favorites(),
          context.previousFavorites,
        )
      }

      if (context?.previousRecipe) {
        queryClient.setQueryData(
          queryKeys.recipe(recipe.id),
          context.previousRecipe,
        )
      }

      toast.error(getErrorMessage(error, 'Could not update your favorites.'))
    },

    onSuccess: (_data, { recipe, isFavorite }) => {
      toast.success(
        isFavorite
          ? `Removed “${recipe.name}” from favorites`
          : `Saved “${recipe.name}” to favorites`,
      )
    },

    onSettled: (_data, _error, { recipe }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeyRoots.favorites })
      void queryClient.invalidateQueries({
        queryKey: queryKeys.recipe(recipe.id),
      })
    },
  })
}
