import { Star } from 'lucide-react'
import { useRef, useState } from 'react'

import { cn } from '@/lib/utils'

export type StarRatingSize = 'sm' | 'md' | 'lg' | 'xl'

const STAR_SIZE: Record<StarRatingSize, string> = {
  sm: 'size-[17px]',
  md: 'size-[19px]',
  lg: 'size-[24px]',
  xl: 'size-[26px]',
}

/**
 * Interactive stars keep a 40px tall hit area whatever the glyph measures; the
 * negative margin stops that from inflating the box the row sits in.
 */
const HIT_AREA: Record<StarRatingSize, string> = {
  sm: 'h-10 w-6 -my-2.5',
  md: 'h-10 w-8 -my-2.5',
  lg: 'h-10 w-10 -my-2',
  xl: 'h-10 w-10 -my-1.5',
}

const ROW_GAP: Record<StarRatingSize, string> = {
  sm: 'gap-[2px]',
  md: 'gap-[3px]',
  lg: 'gap-[3px]',
  xl: 'gap-[5px]',
}

const VALUES = [1, 2, 3, 4, 5] as const

interface StarRatingProps {
  /** `null` renders five empty stars. */
  value: number | null | undefined
  size?: StarRatingSize
  /** Omit to render a static rating. */
  onChange?: (value: number) => void
  disabled?: boolean
  /** Names the control for screen readers, e.g. "Rate Chicken Soup". */
  label?: string
  className?: string
}

function StarIcon({ filled, size }: { filled: boolean; size: StarRatingSize }) {
  return (
    <Star
      aria-hidden
      strokeWidth={0}
      className={cn(
        STAR_SIZE[size],
        'shrink-0 transition-colors',
        filled ? 'fill-star' : 'fill-star-empty',
      )}
    />
  )
}

/**
 * Five stars, readonly or clickable.
 *
 * Interactive mode is a radio group with roving focus: Tab reaches the current
 * rating, the arrow keys move and select, which is what a keyboard user expects
 * from a rating control. Hovering previews a value without committing it.
 */
export function StarRating({
  value,
  size = 'md',
  onChange,
  disabled = false,
  label,
  className,
}: StarRatingProps) {
  const [hovered, setHovered] = useState<number | null>(null)
  const buttons = useRef<(HTMLButtonElement | null)[]>([])

  const current = value ?? 0
  const shown = hovered ?? current

  if (!onChange) {
    return (
      <div
        className={cn('flex items-center', ROW_GAP[size], className)}
        role="img"
        aria-label={`${current} out of 5 stars`}
      >
        {VALUES.map((star) => (
          <StarIcon key={star} filled={star <= current} size={size} />
        ))}
      </div>
    )
  }

  function move(next: number) {
    const clamped = Math.min(5, Math.max(1, next))

    onChange?.(clamped)
    buttons.current[clamped - 1]?.focus()
  }

  return (
    <div
      role="radiogroup"
      aria-label={label ?? 'Your rating'}
      className={cn('flex items-center', ROW_GAP[size], className)}
      onMouseLeave={() => {
        setHovered(null)
      }}
    >
      {VALUES.map((star) => (
        <button
          key={star}
          type="button"
          role="radio"
          ref={(node) => {
            buttons.current[star - 1] = node
          }}
          disabled={disabled}
          aria-checked={star === current}
          aria-label={`${star} ${star === 1 ? 'star' : 'stars'}`}
          // Only the selected star — or the first one, while nothing is picked —
          // is in the tab order; the arrow keys move within the group.
          tabIndex={star === current || (current === 0 && star === 1) ? 0 : -1}
          onMouseEnter={() => {
            setHovered(star)
          }}
          onClick={() => {
            onChange(star)
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
              event.preventDefault()
              move(current + 1)
            }

            if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
              event.preventDefault()
              move(current - 1)
            }
          }}
          className={cn(
            'flex cursor-pointer items-center justify-center rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60',
            HIT_AREA[size],
          )}
        >
          <StarIcon filled={star <= shown} size={size} />
        </button>
      ))}
    </div>
  )
}
