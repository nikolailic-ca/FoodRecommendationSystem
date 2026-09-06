import type { RecipeImage } from '@/api/types'

import { cn } from '@/lib/utils'

interface PhotoCreditProps {
  image: RecipeImage
  className?: string
}

/**
 * Pexels asks for the photographer to be named next to the photo, which is the
 * only reason a recipe page carries a caption at all.
 */
export function PhotoCredit({ image, className }: PhotoCreditProps) {
  if (!image.photographer) {
    return null
  }

  return (
    <p className={cn('text-[12.5px] font-medium text-ink-faint', className)}>
      Photo by{' '}
      {image.photographer_url ? (
        <a
          href={image.photographer_url}
          target="_blank"
          rel="noreferrer noopener"
          className="text-ink-faint underline underline-offset-2 hover:text-foreground"
        >
          {image.photographer}
        </a>
      ) : (
        image.photographer
      )}{' '}
      on{' '}
      {image.source_url ? (
        <a
          href={image.source_url}
          target="_blank"
          rel="noreferrer noopener"
          className="text-ink-faint underline underline-offset-2 hover:text-foreground"
        >
          Pexels
        </a>
      ) : (
        'Pexels'
      )}
    </p>
  )
}
