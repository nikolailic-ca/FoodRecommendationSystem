import { ArrowLeft, Bookmark, ChefHat } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingScreen } from '@/components/common/LoadingScreen'
import { CookingMode } from '@/components/recipe/CookingMode'
import { NutritionPanel } from '@/components/recipe/NutritionPanel'
import { PhotoCredit } from '@/components/recipe/PhotoCredit'
import { RecipeImage } from '@/components/recipe/RecipeImage'
import { RecipeMeta } from '@/components/recipe/RecipeMeta'
import { SimilarRecipes } from '@/components/recipe/SimilarRecipes'
import { StarRating } from '@/components/recipe/StarRating'
import { TagChip } from '@/components/recipe/TagChip'
import { Button } from '@/components/ui/button'
import { useToggleFavorite } from '@/hooks/useFavorites'
import { useDeleteRating, useRateRecipe } from '@/hooks/useRatings'
import { useRecipe } from '@/hooks/useRecipe'
import { useSimilar } from '@/hooks/useSimilar'
import { cn } from '@/lib/utils'

const exactCount = new Intl.NumberFormat('en-GB')

/**
 * The recipe page shows every tag, but Food.com recipes routinely carry thirty
 * of them; beyond this many the chips become a wall that buries the buttons
 * under it, so the rest go behind a toggle.
 */
const COLLAPSED_TAGS = 12

/**
 * Some Food.com descriptions are a paragraph, others are somebody's entire
 * review. Past this many characters the text is clamped so it cannot push the
 * buttons and the rating box off the screen.
 */
const LONG_DESCRIPTION = 320

function parseRecipeId(value: string | undefined): number | null {
  if (value === undefined) {
    return null
  }

  const parsed = Number.parseInt(value, 10)

  return Number.isInteger(parsed) ? parsed : null
}

/**
 * One recipe in full.
 *
 * Ingredients and steps arrive as arrays from the API and are rendered as
 * arrays — there is no string parsing anywhere on this page.
 *
 * Everything below is per-recipe state: which tags are expanded, whether the
 * description is unclamped, and — inside `CookingMode` — which ingredients and
 * steps have been ticked off. The wrapper keys this component on the recipe id
 * so React throws all of it away when the route changes; without that, a single
 * route element reused across recipes shows one recipe's checkmarks on another.
 */
function RecipeDetailsView({ id }: { id: number }) {
  const { data: recipe, error, isPending, isError, refetch } = useRecipe(id)
  const similar = useSimilar(id)

  const rate = useRateRecipe()
  const removeRating = useDeleteRating()
  const toggleFavorite = useToggleFavorite()

  const [cooking, setCooking] = useState(false)
  const [allTags, setAllTags] = useState(false)
  const [fullDescription, setFullDescription] = useState(false)

  if (isPending) {
    return <LoadingScreen fullscreen={false} label="Loading the recipe…" />
  }

  if (isError) {
    return (
      <ErrorState
        title="Could not load this recipe"
        error={error}
        onRetry={() => void refetch()}
      />
    )
  }

  return (
    <>
      <Link
        to="/home"
        className="mb-[22px] inline-flex items-center gap-[7px] rounded-md text-sm font-semibold text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <ArrowLeft className="size-4" strokeWidth={1.9} />
        Back to recommendations
      </Link>

      <div className="mb-14 grid gap-10 lg:grid-cols-2 lg:gap-12">
        <div className="flex flex-col gap-2.5">
          <div className="aspect-[4/3] overflow-hidden rounded-3xl">
            <RecipeImage
              recipeId={recipe.id}
              name={recipe.name}
              tags={recipe.tags}
              imageUrl={recipe.image_url}
              iconSize={92}
            />
          </div>

          {recipe.image ? <PhotoCredit image={recipe.image} /> : null}
        </div>

        <div className="flex flex-col">
          <h1 className="text-[32px] leading-[1.1] font-extrabold tracking-[-0.04em] text-balance capitalize sm:text-[40px]">
            {recipe.name}
          </h1>

          {recipe.description ? (
            <div className="mt-4">
              <p
                className={cn(
                  'text-base leading-[1.6] text-pretty text-ink-soft',
                  !fullDescription && 'line-clamp-5',
                )}
              >
                {recipe.description}
              </p>

              {recipe.description.length > LONG_DESCRIPTION ? (
                <button
                  type="button"
                  onClick={() => {
                    setFullDescription((previous) => !previous)
                  }}
                  className="mt-1.5 cursor-pointer rounded-md text-[13px] font-bold text-primary transition-colors outline-none hover:text-accent-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  {fullDescription ? 'Show less' : 'Read more'}
                </button>
              ) : null}
            </div>
          ) : null}

          <RecipeMeta
            className="mt-[22px]"
            size="md"
            withLabels
            minutes={recipe.minutes}
            calories={recipe.calories}
            ingredientCount={recipe.n_ingredients}
            stepCount={recipe.n_steps}
          />

          <div className="mt-[18px] flex flex-wrap items-center gap-2">
            <StarRating value={Math.round(recipe.avg_rating ?? 0)} size="sm" />

            {recipe.avg_rating === null ? (
              <span className="text-sm font-medium text-muted-foreground">
                No ratings yet
              </span>
            ) : (
              <>
                <span className="text-[15px] font-bold">
                  {recipe.avg_rating.toFixed(1)}
                </span>
                <span className="text-sm font-medium text-muted-foreground">
                  from {exactCount.format(recipe.rating_count)}{' '}
                  {recipe.rating_count === 1 ? 'rating' : 'ratings'}
                </span>
              </>
            )}
          </div>

          {recipe.tags.length > 0 ? (
            <div className="mt-[22px] flex flex-wrap items-center gap-2">
              {(allTags
                ? recipe.tags
                : recipe.tags.slice(0, COLLAPSED_TAGS)
              ).map((tag) => (
                <TagChip key={tag} tag={tag} size="md" interactive />
              ))}

              {recipe.tags.length > COLLAPSED_TAGS ? (
                <button
                  type="button"
                  onClick={() => {
                    setAllTags((previous) => !previous)
                  }}
                  className="cursor-pointer rounded-full px-2 py-1.5 text-[13px] font-bold text-primary transition-colors outline-none hover:text-accent-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  {allTags
                    ? 'Show fewer'
                    : `+${recipe.tags.length - COLLAPSED_TAGS} more`}
                </button>
              ) : null}
            </div>
          ) : null}

          <div className="mt-[26px] flex flex-wrap items-center gap-3">
            <Button
              className="h-12 gap-2.5 rounded-[14px] px-[22px] text-[15px] font-bold shadow-[0_3px_12px_rgba(63,163,77,0.3)]"
              onClick={() => {
                setCooking(true)
              }}
            >
              <ChefHat className="size-[19px]" strokeWidth={1.9} />
              Cooking mode
            </Button>

            <Button
              variant="outline"
              className="h-12 gap-2.5 rounded-[14px] px-5 text-[15px] font-bold"
              disabled={toggleFavorite.isPending}
              onClick={() => {
                toggleFavorite.mutate({
                  recipe,
                  isFavorite: recipe.is_favorite,
                })
              }}
            >
              <Bookmark
                className={`size-[19px] ${recipe.is_favorite ? 'fill-primary text-primary' : ''}`}
                strokeWidth={1.9}
              />
              {recipe.is_favorite ? 'Saved' : 'Save'}
            </Button>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-[18px] border border-border bg-muted/40 px-5 py-4">
            <div className="flex items-center gap-3.5">
              <span className="text-sm font-bold">Your rating</span>
              <StarRating
                value={recipe.user_rating}
                size="lg"
                disabled={rate.isPending}
                label={`Your rating for ${recipe.name}`}
                onChange={(value) => {
                  rate.mutate({ recipeId: recipe.id, rating: value })
                }}
              />
            </div>

            {recipe.user_rating === null ? null : (
              <button
                type="button"
                disabled={removeRating.isPending}
                onClick={() => {
                  removeRating.mutate(recipe.id)
                }}
                className="cursor-pointer rounded-md px-1 text-[13.5px] font-semibold text-muted-foreground transition-colors outline-none hover:text-destructive focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60"
              >
                Remove rating
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="mb-15 grid gap-10 lg:grid-cols-[416px_minmax(0,1fr)] lg:gap-12">
        <div className="flex flex-col gap-6">
          <section className="rounded-3xl border border-border bg-card p-7">
            <div className="mb-[18px] flex items-baseline justify-between">
              <h2 className="text-xl font-extrabold tracking-[-0.025em]">
                Ingredients
              </h2>
              <span className="text-[13px] font-semibold text-muted-foreground">
                {recipe.ingredients.length}{' '}
                {recipe.ingredients.length === 1 ? 'item' : 'items'}
              </span>
            </div>

            <ul className="flex flex-col">
              {recipe.ingredients.map((ingredient, index) => (
                <li
                  key={`${index}-${ingredient}`}
                  className="flex items-center gap-3 border-b border-border py-[9px] text-[15px] font-medium last:border-b-0"
                >
                  <span
                    aria-hidden
                    className="size-1.5 shrink-0 rounded-full bg-primary"
                  />
                  {ingredient}
                </li>
              ))}
            </ul>
          </section>

          <NutritionPanel nutrition={recipe.nutrition} />
        </div>

        <section>
          <h2 className="mb-5 text-xl font-extrabold tracking-[-0.025em]">
            Steps
          </h2>

          <ol className="flex flex-col gap-[18px]">
            {recipe.steps.map((step, index) => (
              <li
                key={`${index}-${step.slice(0, 24)}`}
                className="flex items-start gap-4"
              >
                <span className="flex size-[30px] shrink-0 items-center justify-center rounded-full bg-accent text-sm font-extrabold text-accent-foreground">
                  {index + 1}
                </span>
                <p className="pt-[3px] text-[15.5px] leading-[1.6]">{step}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <SimilarRecipes
        items={similar.data}
        isPending={similar.isPending}
        error={similar.error}
        onRetry={() => void similar.refetch()}
      />

      <CookingMode
        open={cooking}
        onOpenChange={setCooking}
        name={recipe.name}
        ingredients={recipe.ingredients}
        steps={recipe.steps}
      />
    </>
  )
}

/**
 * Reads the recipe out of the URL and hands it to the page as a key, so that
 * navigating from one recipe to another remounts rather than reuses the view.
 */
function RecipeDetails() {
  const { recipeId } = useParams()
  const id = parseRecipeId(recipeId)

  if (id === null) {
    return (
      <ErrorState
        title="Unknown recipe"
        description="That link does not point at a recipe we know."
      />
    )
  }

  return <RecipeDetailsView key={id} id={id} />
}

export default RecipeDetails
