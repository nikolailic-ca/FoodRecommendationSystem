import { X } from 'lucide-react'

import {
  hasActiveFilters,
  maxMinutesLabel,
  type RecommendationFilters,
} from '@/lib/filters'
import { cn } from '@/lib/utils'

interface ActiveFilterChipsProps {
  value: RecommendationFilters
  onChange: (value: RecommendationFilters) => void
  onClear: () => void
  className?: string
}

interface Chip {
  id: string
  label: string
  remove: () => RecommendationFilters
}

/**
 * What is currently narrowing the grid, and one click to undo any of it.
 *
 * Removing a chip applies immediately — unlike the bar, which waits for Apply —
 * because a chip *is* an applied filter, so there is no draft to hold.
 */
export function ActiveFilterChips({
  value,
  onChange,
  onClear,
  className,
}: ActiveFilterChipsProps) {
  if (!hasActiveFilters(value)) {
    return null
  }

  const chips: Chip[] = []

  if (value.query !== '') {
    chips.push({
      id: 'query',
      label: value.query,
      remove: () => ({ ...value, query: '' }),
    })
  }

  if (value.maxMinutes !== null) {
    chips.push({
      id: 'max',
      label: maxMinutesLabel(value.maxMinutes).toLowerCase(),
      remove: () => ({ ...value, maxMinutes: null }),
    })
  }

  for (const ingredient of value.ingredients) {
    chips.push({
      id: `ing:${ingredient}`,
      label: ingredient,
      remove: () => ({
        ...value,
        ingredients: value.ingredients.filter((item) => item !== ingredient),
      }),
    })
  }

  for (const tag of value.tags) {
    chips.push({
      id: `tag:${tag}`,
      label: tag,
      remove: () => ({
        ...value,
        tags: value.tags.filter((item) => item !== tag),
      }),
    })
  }

  return (
    <div className={cn('mb-7 flex flex-wrap items-center gap-2', className)}>
      {chips.map((chip) => (
        <button
          key={chip.id}
          type="button"
          onClick={() => {
            onChange(chip.remove())
          }}
          aria-label={`Remove filter ${chip.label}`}
          className="flex cursor-pointer items-center gap-[7px] rounded-full bg-accent py-1.5 pr-2.5 pl-3 text-[13px] font-semibold text-accent-foreground transition-colors outline-none hover:bg-accent/70 focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {chip.label}
          <X className="size-3.5" />
        </button>
      ))}

      <button
        type="button"
        onClick={onClear}
        className="ml-1.5 cursor-pointer rounded-md px-1 text-[13px] font-semibold text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        Clear all
      </button>
    </div>
  )
}
