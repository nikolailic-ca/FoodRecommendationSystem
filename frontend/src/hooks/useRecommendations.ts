import { useInfiniteQuery, type InfiniteData } from '@tanstack/react-query'
import { useMemo } from 'react'

import { getRecommendations } from '@/api/recommendations'
import type {
  RecommendationItem,
  RecommendationModel,
  RecommendationResponse,
} from '@/api/types'
import {
  normalizeFilters,
  toRecommendationParams,
  type RecommendationFilters,
} from '@/lib/filters'
import { queryKeys } from '@/lib/queryKeys'

export const RECOMMENDATIONS_PAGE_SIZE = 12

export interface RecommendationsPage {
  items: RecommendationItem[]
  total: number
  model: RecommendationModel | null
}

function flatten(
  data: InfiniteData<RecommendationResponse, number>,
): RecommendationsPage {
  const items = data.pages.flatMap((page) => page.items)

  // The newest page carries the freshest count — the pool shrinks as the user
  // rates. It can never be smaller than what is already on screen, though:
  // every loaded card is by definition a recipe that matched.
  const latest = data.pages.at(-1)

  return {
    items,
    total: Math.max(latest?.total_candidates ?? 0, items.length),
    model: data.pages[0]?.model ?? null,
  }
}

/**
 * The recommendation grid, twelve at a time.
 *
 * `total_candidates` is the number of recipes that match the filters and are
 * not yet rated, so the page cursor — the count of items already loaded — walks
 * towards it and stops there. A short page is *not* an ending on its own: the
 * model path pads its results out of a wider pool, so a page can come back
 * under `n` with more still behind it. A page with nothing in it is the ending,
 * and stopping on that is also what keeps the cursor from standing still and
 * asking for the same offset forever.
 *
 * Filters are normalised before they reach the query key, which keeps the cache
 * from splitting over cosmetic differences such as chip order or casing.
 */
export function useRecommendations(filters: RecommendationFilters) {
  const normalized = useMemo(() => normalizeFilters(filters), [filters])

  return useInfiniteQuery({
    queryKey: queryKeys.recommendations(normalized),
    queryFn: ({ pageParam }) =>
      getRecommendations({
        n: RECOMMENDATIONS_PAGE_SIZE,
        offset: pageParam,
        ...toRecommendationParams(normalized),
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (lastPage.items.length === 0) {
        return undefined
      }

      const loaded = allPages.reduce((sum, page) => sum + page.items.length, 0)

      return loaded >= lastPage.total_candidates ? undefined : loaded
    },
    select: flatten,
  })
}
