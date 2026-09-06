import { createElement, useState } from 'react'

import { categoryIconFor, hashId } from '@/lib/placeholder'
import { cn } from '@/lib/utils'

interface RecipeImageProps {
  recipeId: number
  /** Used as the alt text; the tile itself is decorative. */
  name: string
  /** Drives which category glyph the tile falls back to. */
  tags: string[]
  imageUrl?: string | null
  /** Edge length of the glyph, in pixels. 58 on a card, 92 on the hero. */
  iconSize?: number
  className?: string
}

/**
 * The picture at the top of every card and at the top of the recipe page.
 *
 * The dataset ships no photography, so a missing — or broken — `image_url`
 * falls back to the generated tile: a gradient chosen from the recipe id and a
 * glyph chosen from its tags. Both live in `lib/placeholder`, so the tile a
 * recipe gets is identical everywhere it appears.
 */
export function RecipeImage({
  recipeId,
  name,
  tags,
  imageUrl,
  iconSize = 58,
  className,
}: RecipeImageProps) {
  // Remembering *which* url failed, rather than a boolean, means a recycled
  // component instance showing a different recipe still tries its photo.
  const [failedUrl, setFailedUrl] = useState<string | null>(null)

  if (imageUrl && failedUrl !== imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={name}
        loading="lazy"
        decoding="async"
        onError={() => {
          setFailedUrl(imageUrl)
        }}
        className={cn('size-full object-cover', className)}
      />
    )
  }

  const tint = hashId(recipeId)
  const icon = categoryIconFor(tags)

  return (
    <div
      aria-hidden
      className={cn('flex size-full items-center justify-center', className)}
      style={{ backgroundImage: tint.gradient }}
    >
      {createElement(icon, {
        strokeWidth: 1.4,
        className: 'opacity-90',
        style: { width: iconSize, height: iconSize, color: tint.ink },
      })}
    </div>
  )
}
