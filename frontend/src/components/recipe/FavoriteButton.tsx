import { Bookmark } from 'lucide-react'
import type { MouseEvent } from 'react'

import type { RecipeCard } from '@/api/types'
import { useFavoriteIds, useToggleFavorite } from '@/hooks/useFavorites'
import { cn } from '@/lib/utils'

interface FavoriteButtonProps {
  recipe: RecipeCard
  /**
   * Overrides the cached favourites list — the recipe page knows its own
   * `is_favorite` before the list has loaded.
   */
  isFavorite?: boolean
  className?: string
}

/**
 * The bookmark that sits on a card image.
 *
 * It lives inside the `Link` that wraps the whole card, so both the default
 * navigation and the click bubbling up to it have to be stopped; without that,
 * saving a recipe would also open it.
 */
export function FavoriteButton({
  recipe,
  isFavorite,
  className,
}: FavoriteButtonProps) {
  const { data: favoriteIds } = useFavoriteIds()
  const toggle = useToggleFavorite()

  const saved = isFavorite ?? favoriteIds?.has(recipe.id) ?? false

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()

    toggle.mutate({ recipe, isFavorite: saved })
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-pressed={saved}
      aria-label={saved ? `Remove ${recipe.name} from favorites` : `Save ${recipe.name} to favorites`}
      className={cn(
        'flex size-9 cursor-pointer items-center justify-center rounded-full bg-background shadow-[0_2px_10px_rgba(16,24,40,0.22)] transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
        saved ? 'text-primary' : 'text-muted-foreground hover:text-foreground',
        className,
      )}
    >
      <Bookmark
        className={cn('size-[17px]', saved && 'fill-primary')}
        strokeWidth={1.9}
      />
    </button>
  )
}
