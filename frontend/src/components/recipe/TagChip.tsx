import { Link } from 'react-router-dom'

import { tagFilterHref } from '@/lib/filters'
import { cn } from '@/lib/utils'

interface TagChipProps {
  tag: string
  /** Links to the filtered home grid instead of rendering plain text. */
  interactive?: boolean
  size?: 'sm' | 'md'
  className?: string
}

const SIZES = {
  sm: 'px-2.5 py-1 text-xs',
  md: 'px-[13px] py-1.5 text-[13px]',
} as const

/** One grey pill. Clickable everywhere except inside a card, where the card owns the click. */
export function TagChip({
  tag,
  interactive = false,
  size = 'sm',
  className,
}: TagChipProps) {
  const classes = cn(
    'inline-flex shrink-0 items-center rounded-full bg-secondary font-semibold tracking-[-0.01em] text-ink-soft',
    SIZES[size],
    interactive &&
      'transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:ring-3 focus-visible:ring-ring/50 outline-none',
    className,
  )

  if (!interactive) {
    return <span className={classes}>{tag}</span>
  }

  return (
    <Link to={tagFilterHref(tag)} className={classes}>
      {tag}
    </Link>
  )
}
