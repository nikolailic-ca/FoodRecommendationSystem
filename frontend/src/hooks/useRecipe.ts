import { useQuery } from '@tanstack/react-query'

import { getRecipe } from '@/api/recipes'
import { queryKeys } from '@/lib/queryKeys'

/** One recipe with its steps, ingredients, nutrition and the user's rating. */
export function useRecipe(recipeId: number | null) {
  const enabled = recipeId !== null && Number.isInteger(recipeId)

  return useQuery({
    queryKey: queryKeys.recipe(recipeId ?? -1),
    queryFn: () => getRecipe(recipeId ?? -1),
    enabled,
  })
}
