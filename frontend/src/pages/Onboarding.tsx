import { useQueryClient } from '@tanstack/react-query'
import { ArrowRight, ChefHat } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { RatingEntry } from '@/api/types'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/layout/PageHeader'
import { RecipeCard } from '@/components/recipe/RecipeCard'
import { RecipeGrid, RecipeGridSkeleton } from '@/components/recipe/RecipeGrid'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { useLogout } from '@/hooks/useLogout'
import { useMe } from '@/hooks/useMe'
import { useOnboardingRecipes } from '@/hooks/useOnboardingRecipes'
import { useRateRecipe, useRatings } from '@/hooks/useRatings'
import { MIN_ONBOARDING_RATINGS } from '@/lib/constants'
import { queryKeyRoots } from '@/lib/queryKeys'

function OnboardingHeader() {
  const logout = useLogout()

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex h-[68px] max-w-7xl items-center px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-[10px] bg-primary text-primary-foreground">
            <ChefHat className="size-[18px]" />
          </span>
          <span className="text-lg font-extrabold tracking-[-0.03em]">
            FoodRec
          </span>
        </div>

        <div className="grow" />

        <button
          type="button"
          onClick={logout}
          className="cursor-pointer rounded-md px-1 text-sm font-semibold text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          Log out
        </button>
      </div>
    </header>
  )
}

function toRatingMap(entries: RatingEntry[] | undefined): Map<number, number> {
  return new Map(entries?.map((entry) => [entry.recipe.id, entry.rating]))
}

/**
 * First run: rate five recipes so the model has something to learn from.
 *
 * Ratings are written straight through on every click. The local overlay is
 * what makes the stars fill instantly — the ratings query behind it is the
 * source of truth, so reloading the page keeps whatever was already rated.
 */
function Onboarding() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const me = useMe()
  const recipes = useOnboardingRecipes()
  const ratings = useRatings()
  const rate = useRateRecipe()

  const [pending, setPending] = useState<Map<number, number>>(new Map())
  const [continuing, setContinuing] = useState(false)

  const saved = toRatingMap(ratings.data)
  const combined = new Map([...saved, ...pending])

  const rated = Math.max(me.data?.ratings_count ?? 0, combined.size)

  // Display only. The threshold itself lives in `settings.onboarding_min_ratings`
  // on the server, so this number drives the copy and the progress bar and
  // nothing else.
  const remaining = Math.max(0, MIN_ONBOARDING_RATINGS - rated)

  // The gate is the server's own answer, which is exactly what the route guard
  // reads. Recomputing it here is how the button ends up enabled while the
  // guard still says no and bounces the user straight back.
  const canContinue = me.data?.onboarding_completed === true

  function statusMessage(): string {
    if (canContinue) {
      return 'Keep rating to sharpen things, or continue.'
    }

    if (remaining > 0) {
      return `Rate ${remaining} more to continue. You can add more later.`
    }

    return 'Saving your ratings…'
  }

  function handleRate(recipeId: number, value: number) {
    setPending((previous) => new Map(previous).set(recipeId, value))

    rate.mutate(
      { recipeId, rating: value },
      {
        // `useRateRecipe` cannot reach this map, so the rollback has to happen
        // here: a rating that never reached the server must not keep a star
        // filled or count towards the progress above.
        onError: () => {
          setPending((previous) => {
            if (previous.get(recipeId) !== value) {
              // Already superseded by a later click; leave that one alone.
              return previous
            }

            const next = new Map(previous)
            next.delete(recipeId)

            return next
          })
        },
      },
    )
  }

  async function handleContinue() {
    setContinuing(true)

    try {
      // The route guard reads `onboarding_completed` off `['me']`. Navigating
      // before that has been refetched would bounce straight back here.
      await queryClient.invalidateQueries({ queryKey: queryKeyRoots.me })
      await queryClient.invalidateQueries({
        queryKey: queryKeyRoots.recommendations,
        refetchType: 'none',
      })
      navigate('/home', { replace: true })
    } finally {
      setContinuing(false)
    }
  }

  return (
    <div className="min-h-dvh bg-background">
      <OnboardingHeader />

      <main className="mx-auto max-w-7xl px-4 pt-10 pb-8 sm:px-6 lg:px-8">
        <PageHeader
          eyebrow="Getting started"
          title="Tell us what you like"
          className="mb-3"
        />

        <p className="mb-8 max-w-[720px] text-base leading-[1.6] text-ink-soft">
          Rate at least {MIN_ONBOARDING_RATINGS} of these recipes. The model
          learns from what you rate, so the more you rate, the sharper the
          recommendations get.
        </p>

        {recipes.isPending ? <RecipeGridSkeleton count={8} /> : null}

        {recipes.isError ? (
          <ErrorState
            error={recipes.error}
            onRetry={() => void recipes.refetch()}
          />
        ) : null}

        {recipes.data?.length === 0 ? (
          <ErrorState
            title="No recipes to rate just yet"
            description="The starter deck came back empty. That is usually momentary — try again."
            onRetry={() => void recipes.refetch()}
          />
        ) : null}

        {recipes.data && recipes.data.length > 0 ? (
          <RecipeGrid>
            {recipes.data.map((recipe) => (
              <RecipeCard
                key={recipe.id}
                recipe={recipe}
                variant="compact"
                userRating={combined.get(recipe.id) ?? null}
                onRate={(value) => {
                  handleRate(recipe.id, value)
                }}
              />
            ))}
          </RecipeGrid>
        ) : null}

        <div className="sticky bottom-4 z-20 mt-8 flex flex-col gap-4 rounded-[20px] border border-border bg-card px-6 py-[18px] shadow-[0_-2px_24px_-12px_rgba(16,24,40,0.3)] lg:flex-row lg:items-center lg:gap-6">
          <div className="flex w-full max-w-[420px] flex-col gap-2">
            <span className="text-sm font-bold">
              {Math.min(rated, MIN_ONBOARDING_RATINGS)} of{' '}
              {MIN_ONBOARDING_RATINGS} rated
            </span>
            <Progress
              aria-label="Onboarding progress"
              value={(Math.min(rated, MIN_ONBOARDING_RATINGS) / MIN_ONBOARDING_RATINGS) * 100}
              className="h-1.5 bg-muted"
            />
          </div>

          <span className="text-[13.5px] font-medium text-muted-foreground">
            {statusMessage()}
          </span>

          <div className="hidden grow lg:block" />

          <Button
            type="button"
            disabled={!canContinue || continuing}
            onClick={() => void handleContinue()}
            className="h-12 shrink-0 gap-2.5 rounded-[14px] px-7 text-[15px] font-bold"
          >
            {continuing ? 'Loading…' : 'Continue'}
            <ArrowRight className="size-[18px]" strokeWidth={1.9} />
          </Button>
        </div>
      </main>
    </div>
  )
}

export default Onboarding
