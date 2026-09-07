import { ChevronDown } from 'lucide-react'
import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ActiveFilterChips } from '@/components/filters/ActiveFilterChips'
import { FilterBar } from '@/components/filters/FilterBar'
import { FilterSheet } from '@/components/filters/FilterSheet'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/layout/PageHeader'
import { RecipeCard } from '@/components/recipe/RecipeCard'
import { RecipeGrid, RecipeGridSkeleton } from '@/components/recipe/RecipeGrid'
import { Button } from '@/components/ui/button'
import { useRecommendations } from '@/hooks/useRecommendations'
import {
  EMPTY_FILTERS,
  hasActiveFilters,
  parseFilters,
  serializeFilters,
  type RecommendationFilters,
} from '@/lib/filters'
import { formatCount } from '@/lib/format'

function countActive(filters: RecommendationFilters): number {
  return (
    (filters.query === '' ? 0 : 1) +
    (filters.maxMinutes === null ? 0 : 1) +
    filters.ingredients.length +
    filters.tags.length
  )
}

/**
 * The recommendation grid.
 *
 * Every filter lives in the query string, so a filtered view can be linked,
 * reloaded and reached from a tag chip on any card, and the browser's back
 * button restores exactly what was on screen.
 */
function Home() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(() => parseFilters(searchParams), [searchParams])

  const applyFilters = useCallback(
    (next: RecommendationFilters) => {
      setSearchParams(serializeFilters(next), { replace: false })
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
    [setSearchParams],
  )

  const {
    data,
    error,
    isPending,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useRecommendations(filters)

  const loaded = data?.items.length ?? 0
  const total = data?.total ?? 0
  const filtered = hasActiveFilters(filters)

  return (
    <>
      <PageHeader
        eyebrow="Recommended for you"
        title="What should you eat today?"
        actions={
          data ? (
            <span className="text-sm font-medium text-muted-foreground">
              {formatCount(total)} {total === 1 ? 'recipe' : 'recipes'}{' '}
              {filtered ? 'match your filters' : 'to choose from'}
            </span>
          ) : null
        }
      />

      <FilterBar value={filters} onApply={applyFilters} />
      <FilterSheet
        value={filters}
        onApply={applyFilters}
        activeCount={countActive(filters)}
      />

      <ActiveFilterChips
        value={filters}
        onChange={applyFilters}
        onClear={() => {
          applyFilters(EMPTY_FILTERS)
        }}
      />

      {isPending ? <RecipeGridSkeleton count={8} /> : null}

      {isError ? (
        <ErrorState
          title="Could not load your recommendations"
          error={error}
          onRetry={() => void refetch()}
        />
      ) : null}

      {data && loaded === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-3xl border border-black/5 bg-card px-6 py-16 text-center">
          <p className="text-lg font-bold tracking-tight">
            Nothing matches those filters
          </p>
          <p className="max-w-md text-sm text-muted-foreground">
            {filtered
              ? 'Try a longer cooking time, or drop an ingredient.'
              : 'Rate a few more recipes and the model will have more to work with.'}
          </p>

          {filtered ? (
            <Button
              variant="outline"
              className="mt-1 h-11 rounded-xl px-5 font-bold"
              onClick={() => {
                applyFilters(EMPTY_FILTERS)
              }}
            >
              Clear filters
            </Button>
          ) : null}
        </div>
      ) : null}

      {data && loaded > 0 ? (
        <>
          <RecipeGrid>
            {data.items.map((item) => (
              <RecipeCard
                key={item.recipe.id}
                recipe={item.recipe}
                variant="recommendation"
                matchPercent={item.match_percent}
                explanationName={item.explanation?.because_recipe_name}
                explanationRating={item.explanation?.because_rating}
              />
            ))}
          </RecipeGrid>

          <div className="mt-8 flex flex-col items-center gap-2.5">
            {hasNextPage ? (
              <Button
                variant="outline"
                className="h-[46px] gap-2 rounded-full px-[26px] text-sm font-bold"
                disabled={isFetchingNextPage}
                onClick={() => void fetchNextPage()}
              >
                {isFetchingNextPage ? 'Loading…' : 'Load more'}
                <ChevronDown className="size-4" />
              </Button>
            ) : null}

            <span className="text-[13px] font-medium text-muted-foreground">
              Showing {loaded} of {formatCount(total)}
            </span>
          </div>
        </>
      ) : null}
    </>
  )
}

export default Home
