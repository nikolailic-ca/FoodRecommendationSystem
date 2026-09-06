import { ChefHat, Clock, Flame, List } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { formatCalories, formatMinutes } from '@/lib/format'
import { cn } from '@/lib/utils'

interface RecipeMetaProps {
  minutes: number | null
  calories: number | null
  ingredientCount: number | null
  /** Only the recipe page has room for the step count. */
  stepCount?: number | null
  /** "9 ingredients" instead of a bare "9". */
  withLabels?: boolean
  size?: 'sm' | 'md'
  className?: string
}

interface MetaItem {
  id: string
  icon: LucideIcon
  label: string
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

/** Time, energy and size — the three numbers every recipe surface repeats. */
export function RecipeMeta({
  minutes,
  calories,
  ingredientCount,
  stepCount,
  withLabels = false,
  size = 'sm',
  className,
}: RecipeMetaProps) {
  const items: MetaItem[] = []

  if (minutes !== null) {
    items.push({ id: 'minutes', icon: Clock, label: formatMinutes(minutes) })
  }

  if (calories !== null) {
    items.push({ id: 'calories', icon: Flame, label: formatCalories(calories) })
  }

  if (ingredientCount !== null) {
    items.push({
      id: 'ingredients',
      icon: List,
      label: withLabels
        ? plural(ingredientCount, 'ingredient')
        : String(ingredientCount),
    })
  }

  if (stepCount !== null && stepCount !== undefined) {
    items.push({ id: 'steps', icon: ChefHat, label: plural(stepCount, 'step') })
  }

  if (items.length === 0) {
    return null
  }

  return (
    <div
      className={cn(
        'flex flex-wrap items-center text-muted-foreground',
        size === 'sm'
          ? 'gap-x-[13px] gap-y-1 text-[13px] font-medium'
          : 'gap-x-[22px] gap-y-2 text-sm font-semibold',
        className,
      )}
    >
      {items.map(({ id, icon: Icon, label }) => (
        <span key={id} className="flex items-center gap-[5px]">
          <Icon
            className={size === 'sm' ? 'size-[15px]' : 'size-[17px]'}
            strokeWidth={1.9}
          />
          {label}
        </span>
      ))}
    </div>
  )
}
