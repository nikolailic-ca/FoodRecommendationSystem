import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingScreen } from '@/components/common/LoadingScreen'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { useFavoriteIds } from '@/hooks/useFavorites'
import { useRecommendations } from '@/hooks/useRecommendations'
import { parseFilters } from '@/lib/filters'
import { formatCount, formatMinutes } from '@/lib/format'

/**
 * Placeholder: proves the recommendation pipeline end to end — filters read
 * from the URL, paged results, favourite ids. The designed grid replaces the
 * list below without touching the hooks.
 */
function Home() {
  const [searchParams] = useSearchParams()
  const filters = useMemo(() => parseFilters(searchParams), [searchParams])

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

  const favoriteIds = useFavoriteIds()

  return (
    <>
      <PageHeader
        eyebrow="Recommended for you"
        title="What should you eat today?"
        subtitle={`model: ${data?.model ?? '—'} · filters: ${JSON.stringify(filters)}`}
        actions={
          <span className="text-sm text-muted-foreground">
            {formatCount(data?.total ?? 0)} candidates
          </span>
        }
      />

      {isPending ? <LoadingScreen fullscreen={false} /> : null}

      {isError ? <ErrorState error={error} onRetry={() => void refetch()} /> : null}

      {data ? (
        <>
          <p className="mb-4 text-sm text-muted-foreground">
            {data.items.length} loaded · {favoriteIds.data?.size ?? 0} favorites
          </p>

          <ul className="flex flex-col gap-2">
            {data.items.map(({ recipe, match_percent, score, explanation }) => (
              <li
                key={recipe.id}
                className="rounded-2xl border border-black/5 bg-card p-4 text-sm"
              >
                <Link
                  to={`/recipes/${recipe.id}`}
                  className="font-bold text-foreground"
                >
                  {recipe.name}
                </Link>
                <p className="text-muted-foreground">
                  {match_percent}% match · score {score.toFixed(4)} ·{' '}
                  {formatMinutes(recipe.minutes)} · {recipe.avg_rating} (
                  {formatCount(recipe.rating_count)}) ·{' '}
                  {favoriteIds.data?.has(recipe.id) ? 'saved' : 'not saved'}
                </p>
                <p className="text-muted-foreground">
                  tags: {recipe.tags.join(', ') || '—'}
                </p>
                {explanation ? (
                  <p className="text-muted-foreground">
                    because “{explanation.because_recipe_name}” rated{' '}
                    {explanation.because_rating}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>

          {data.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No recommendations for these filters.
            </p>
          ) : null}

          {hasNextPage ? (
            <Button
              variant="outline"
              size="lg"
              className="mt-6"
              disabled={isFetchingNextPage}
              onClick={() => void fetchNextPage()}
            >
              {isFetchingNextPage ? 'Loading…' : 'Load more'}
            </Button>
          ) : null}
        </>
      ) : null}
    </>
  )
}

export default Home
