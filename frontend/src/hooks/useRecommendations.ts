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
  const firstPage = data.pages[0]

  return {
    items: data.pages.flatMap((page) => page.items),
    total: firstPage?.total_candidates ?? 0,
    model: firstPage?.model ?? null,
  }
}

/**
 * The recommendation grid, twelve at a time.
 *
 * The page cursor is the number of items already loaded, so `getNextPageParam`
 * simply stops once that reaches `total_candidates`. Filters are normalised
 * before they reach the query key, which keeps the cache from splitting over
 * cosmetic differences such as chip order or casing.
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
      const loaded = allPages.reduce((sum, page) => sum + page.items.length, 0)

      if (loaded === 0 || loaded >= lastPage.total_candidates) {
        return undefined
      }

      return loaded
    },
    select: flatten,
  })
}
