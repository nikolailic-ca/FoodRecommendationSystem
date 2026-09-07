import { useQuery } from '@tanstack/react-query'

import { getSimilarRecipes } from '@/api/recipes'
import { queryKeys } from '@/lib/queryKeys'

/** Content-based neighbours of a recipe, for the "more like this" strip. */
export function useSimilar(recipeId: number | null, n = 8) {
  const enabled = recipeId !== null && Number.isInteger(recipeId)

  return useQuery({
    queryKey: queryKeys.similar(recipeId ?? -1, n),
    queryFn: () => getSimilarRecipes(recipeId ?? -1, n),
    enabled,
  })
}
