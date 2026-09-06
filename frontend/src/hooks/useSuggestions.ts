import { useQuery } from '@tanstack/react-query'

import { getIngredients, getTags } from '@/api/recipes'
import { queryKeys } from '@/lib/queryKeys'

import { useDebouncedValue } from './useDebouncedValue'

/** Below this, the suggestion list would be noise, so nothing is requested. */
const MIN_QUERY_LENGTH = 2

/**
 * Autocomplete for the ingredient filter.
 *
 * The raw input is debounced into a query key rather than into an effect that
 * writes state, so React owns the render and TanStack Query owns the request,
 * its cancellation and its cache.
 */
export function useIngredientSuggestions(query: string, limit = 10) {
  const debounced = useDebouncedValue(query.trim(), 300)

  return useQuery({
    queryKey: queryKeys.suggestions('ingredients', debounced),
    queryFn: () => getIngredients(debounced, limit),
    enabled: debounced.length >= MIN_QUERY_LENGTH,
  })
}

/** Autocomplete for the tag filter. */
export function useTagSuggestions(query: string, limit = 20) {
  const debounced = useDebouncedValue(query.trim(), 300)

  return useQuery({
    queryKey: queryKeys.suggestions('tags', debounced),
    queryFn: () => getTags(debounced, limit),
    enabled: debounced.length >= MIN_QUERY_LENGTH,
  })
}
