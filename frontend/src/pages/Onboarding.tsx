import { ErrorState } from '@/components/common/ErrorState'
import { LoadingScreen } from '@/components/common/LoadingScreen'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { useMe } from '@/hooks/useMe'
import { useOnboardingRecipes } from '@/hooks/useOnboardingRecipes'
import { useRateRecipe } from '@/hooks/useRatings'
import { MIN_ONBOARDING_RATINGS } from '@/lib/constants'
import { formatMinutes } from '@/lib/format'

const RATING_SCALE = [1, 2, 3, 4, 5] as const

/**
 * Placeholder: the onboarding deck as a flat list, so the rating mutation and
 * the "at least five ratings" rule can be exercised before the designed
 * one-card-at-a-time flow is built.
 */
function Onboarding() {
  const me = useMe()
  const { data, error, isPending, isError, refetch } = useOnboardingRecipes()
  const rate = useRateRecipe()

  const ratingsCount = me.data?.ratings_count ?? 0
  const remaining = Math.max(0, MIN_ONBOARDING_RATINGS - ratingsCount)

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
      <PageHeader
        eyebrow="Onboarding"
        title="Tell us what you like"
        subtitle={`${ratingsCount} of ${MIN_ONBOARDING_RATINGS} ratings · ${remaining} to go`}
      />

      {isPending ? <LoadingScreen fullscreen={false} /> : null}

      {isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : null}

      <ul className="flex flex-col gap-3">
        {data?.map((recipe) => (
          <li
            key={recipe.id}
            className="rounded-2xl border border-black/5 bg-card p-4 text-sm"
          >
            <p className="font-bold">{recipe.name}</p>
            <p className="text-muted-foreground">
              {formatMinutes(recipe.minutes)} · {recipe.description_short}
            </p>
            <div className="mt-2 flex gap-1">
              {RATING_SCALE.map((rating) => (
                <Button
                  key={rating}
                  size="sm"
                  variant="outline"
                  disabled={rate.isPending}
                  onClick={() =>
                    rate.mutate({ recipeId: recipe.id, rating })
                  }
                >
                  {rating}
                </Button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default Onboarding
