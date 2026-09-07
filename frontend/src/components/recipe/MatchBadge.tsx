import { Sparkles } from 'lucide-react'

import { cn } from '@/lib/utils'

interface MatchBadgeProps {
  /** `match_percent` straight from the recommendation payload. */
  value: number
  className?: string
}

/** The orange model score that sits on the top left corner of a card image. */
export function MatchBadge({ value, className }: MatchBadgeProps) {
  return (
    <span
      className={cn(
        'flex items-center gap-[5px] rounded-full bg-match py-1.5 pr-2.5 pl-2 text-xs font-bold tracking-[-0.01em] text-match-foreground shadow-[0_2px_10px_rgba(232,128,31,0.38)]',
        className,
      )}
    >
      <Sparkles className="size-[13px]" strokeWidth={1.9} />
      {Math.round(value)}% match
    </span>
  )
}
