import type { SimilarRecipe } from '@/api/types'
import { ErrorState } from '@/components/common/ErrorState'

import { RecipeCard } from './RecipeCard'
import { RecipeCardSkeleton } from './RecipeGrid'

/** Four neighbours is what the row fits; the API is asked for a few more. */
const SHOWN = 4

interface SimilarRecipesProps {
  items: SimilarRecipe[] | undefined
  isPending: boolean
  error: unknown
  onRetry: () => void
}

/**
 * "You might also like": a four-up row on desktop that turns into a
 * snap-scrolling carousel on a phone, where four cards would be four screens of
 * scrolling on their own.
 */
export function SimilarRecipes({
  items,
  isPending,
  error,
  onRetry,
}: SimilarRecipesProps) {
  if (error) {
    return (
      <section>
        <h2 className="mb-5 text-2xl font-extrabold tracking-[-0.03em]">
          You might also like
        </h2>
        <ErrorState
          title="Could not load similar recipes"
          error={error}
          onRetry={onRetry}
        />
      </section>
    )
  }

  if (!isPending && (items === undefined || items.length === 0)) {
    return null
  }

  const shown = items?.slice(0, SHOWN) ?? []

  return (
    <section>
      <div className="mb-5 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <h2 className="text-2xl font-extrabold tracking-[-0.03em]">
          You might also like
        </h2>
        <span className="text-[13.5px] font-medium text-muted-foreground">
          Close to this dish, ranked for you
        </span>
      </div>

      <div className="-mx-4 flex snap-x snap-mandatory gap-6 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-4">
        {isPending
          ? Array.from({ length: SHOWN }, (_, index) => (
              <div
                key={index}
                className="w-[78vw] shrink-0 snap-start sm:w-auto"
              >
                <RecipeCardSkeleton />
              </div>
            ))
          : shown.map(({ recipe, match_percent }) => (
              <div
                key={recipe.id}
                className="w-[78vw] shrink-0 snap-start sm:w-auto"
              >
                <RecipeCard
                  recipe={recipe}
                  variant="browse"
                  matchPercent={match_percent ?? undefined}
                />
              </div>
            ))}
      </div>
    </section>
  )
}
