import { Star } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { RecipeCard as RecipeCardModel } from '@/api/types'
import { formatCount, formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'

import { FavoriteButton } from './FavoriteButton'
import { MatchBadge } from './MatchBadge'
import { RecipeImage } from './RecipeImage'
import { RecipeMeta } from './RecipeMeta'
import { StarRating } from './StarRating'
import { TagChip } from './TagChip'

/**
 * How many tag chips fit on one line before the rest collapse into "+N".
 *
 * Matched to `CARD_TAG_LIMIT` in `backend/app/services/recipes.py`, which is
 * how many tags a card actually carries. Showing fewer than the API sends turns
 * the last real tag into a "+1" that says nothing. The overflow chip below is
 * kept as a guard in case that server limit ever rises.
 */
const VISIBLE_TAGS = 4

export type RecipeCardVariant =
  | 'recommendation'
  | 'browse'
  | 'rated'
  | 'compact'

interface RecipeCardProps {
  recipe: RecipeCardModel
  variant?: RecipeCardVariant
  /** `recommendation` only: the orange badge and the "because you rated" line. */
  matchPercent?: number
  explanationName?: string
  explanationRating?: number
  /** `rated` only. */
  userRating?: number | null
  onRate?: (rating: number) => void
  onRemoveRating?: () => void
  ratedAt?: string
  className?: string
}

function AverageRating({
  average,
  count,
}: {
  average: number | null
  count: number
}) {
  if (average === null) {
    return (
      <p className="text-[13.5px] font-medium text-muted-foreground">
        No ratings yet
      </p>
    )
  }

  return (
    <div className="flex items-center gap-1.5">
      <Star className="size-[15px] fill-star" strokeWidth={0} aria-hidden />
      <span className="text-[13.5px] font-bold">{average.toFixed(1)}</span>
      <span className="text-[13.5px] font-medium text-muted-foreground">
        ({formatCount(count)})
      </span>
    </div>
  )
}

/**
 * The one card every screen is built from.
 *
 * The whole thing is a link to the recipe, so the two interactive overlays —
 * the bookmark and, on the rated variant, the stars — stop their own clicks
 * from reaching it. The four variants only add or remove rows; the image ratio,
 * the padding and the two-line title height never change, which is what keeps a
 * mixed grid aligned.
 */
export function RecipeCard({
  recipe,
  variant = 'browse',
  matchPercent,
  explanationName,
  explanationRating,
  userRating,
  onRate,
  onRemoveRating,
  ratedAt,
  className,
}: RecipeCardProps) {
  const isCompact = variant === 'compact'
  const hiddenTags = Math.max(0, recipe.tags.length - VISIBLE_TAGS)

  return (
    <article
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-3xl border border-black/5 bg-card shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg focus-within:ring-3 focus-within:ring-ring/50',
        className,
      )}
    >
      <div className="relative aspect-[16/10] overflow-hidden">
        <RecipeImage
          recipeId={recipe.id}
          name={recipe.name}
          tags={recipe.tags}
          imageUrl={recipe.image_url}
          className="transition-transform duration-300 group-hover:scale-[1.03]"
        />

        {variant === 'recommendation' && matchPercent !== undefined ? (
          <MatchBadge value={matchPercent} className="absolute top-3 left-3" />
        ) : null}

        {isCompact ? null : (
          <FavoriteButton
            recipe={recipe}
            className="absolute top-3 right-3 z-10"
          />
        )}
      </div>

      <div className={cn('flex flex-col p-4', isCompact ? 'gap-3' : 'gap-2')}>
        <h3
          className={cn(
            'font-bold tracking-[-0.015em] capitalize',
            isCompact
              ? 'min-h-[43px] text-base leading-[1.34]'
              : 'min-h-[46px] text-[17px] leading-[1.34]',
          )}
        >
          {isCompact ? (
            // Onboarding leaves the card inert on purpose: rating is the only
            // thing to do there, and the recipe page is behind the guard anyway.
            <span className="line-clamp-2">{recipe.name}</span>
          ) : (
            /* Stretched link: the card is one target, without nesting the
               bookmark button inside an anchor. */
            <Link
              to={`/recipes/${recipe.id}`}
              className="line-clamp-2 outline-none before:absolute before:inset-0 before:content-['']"
            >
              {recipe.name}
            </Link>
          )}
        </h3>

        {isCompact ? (
          <div className="relative z-10 w-fit">
            <StarRating
              value={userRating}
              size="xl"
              onChange={onRate}
              label={`Rate ${recipe.name}`}
            />
          </div>
        ) : (
          <>
            <RecipeMeta
              minutes={recipe.minutes}
              calories={recipe.calories}
              ingredientCount={recipe.n_ingredients}
            />

            {variant === 'rated' ? (
              <>
                <div className="relative z-10 flex items-center justify-between gap-2 rounded-xl border border-border bg-muted/40 px-2.5 py-2">
                  <StarRating
                    value={userRating}
                    size="md"
                    onChange={onRate}
                    label={`Your rating for ${recipe.name}`}
                  />

                  {onRemoveRating ? (
                    <button
                      type="button"
                      onClick={onRemoveRating}
                      className="cursor-pointer rounded-md px-1 text-xs font-semibold text-muted-foreground transition-colors outline-none hover:text-destructive focus-visible:ring-3 focus-visible:ring-ring/50"
                    >
                      Remove
                    </button>
                  ) : null}
                </div>

                <p className="text-[12.5px] leading-[1.4] text-muted-foreground">
                  {ratedAt ? `Rated ${formatDate(ratedAt)}` : null}
                </p>
              </>
            ) : (
              <>
                <AverageRating
                  average={recipe.avg_rating}
                  count={recipe.rating_count}
                />

                <div className="relative z-10 flex flex-wrap gap-1.5">
                  {recipe.tags.slice(0, VISIBLE_TAGS).map((tag) => (
                    <TagChip key={tag} tag={tag} interactive />
                  ))}

                  {hiddenTags > 0 ? <TagChip tag={`+${hiddenTags}`} /> : null}
                </div>

                <p className="min-h-[35px] text-[12.5px] leading-[1.4] text-muted-foreground">
                  {/* `because_rating` defaults to 0 server-side when the model
                      cannot name the rating behind a recommendation, and
                      "because you rated X 0 stars" is not a sentence. */}
                  {explanationName &&
                  explanationRating !== undefined &&
                  explanationRating > 0 ? (
                    <>
                      Because you rated{' '}
                      <span className="font-semibold text-foreground capitalize">
                        {explanationName}
                      </span>{' '}
                      {explanationRating}{' '}
                      {explanationRating === 1 ? 'star' : 'stars'}
                    </>
                  ) : null}
                </p>
              </>
            )}
          </>
        )}
      </div>
    </article>
  )
}
