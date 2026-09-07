import type { Nutrition } from '@/api/types'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

interface NutritionPanelProps {
  nutrition: Nutrition
  className?: string
}

/** Ordered the way the design sheet lists them, not the way the API returns them. */
const ROWS = [
  { key: 'protein_pdv', label: 'Protein' },
  { key: 'saturated_fat_pdv', label: 'Saturated fat' },
  { key: 'total_fat_pdv', label: 'Total fat' },
  { key: 'sodium_pdv', label: 'Sodium' },
  { key: 'sugar_pdv', label: 'Sugar' },
  { key: 'carbohydrates_pdv', label: 'Carbohydrates' },
] as const satisfies readonly { key: keyof Nutrition; label: string }[]

/**
 * Calories as a headline, then the six percent-of-daily-value bars.
 *
 * The dataset happily records values far above 100% — a whole cake is 900% of
 * the daily sugar — so the bar is capped while the number itself is not.
 */
export function NutritionPanel({ nutrition, className }: NutritionPanelProps) {
  return (
    <section
      className={cn('rounded-3xl border border-border bg-card p-7', className)}
    >
      <h2 className="mb-[18px] text-xl font-extrabold tracking-[-0.025em]">
        Nutrition
      </h2>

      <div className="mb-[18px] flex items-baseline gap-2.5 border-b border-border pb-[18px]">
        <span className="text-[40px] leading-none font-extrabold tracking-[-0.04em]">
          {nutrition.calories === null ? '—' : Math.round(nutrition.calories)}
        </span>
        <span className="text-sm font-semibold text-muted-foreground">
          kcal per serving
        </span>
      </div>

      <dl className="flex flex-col gap-[15px]">
        {ROWS.map(({ key, label }) => {
          const value = nutrition[key]

          return (
            <div key={key} className="flex flex-col gap-[7px]">
              <div className="flex justify-between text-[13.5px] font-semibold">
                <dt className="text-ink-soft">{label}</dt>
                <dd>{value === null ? '—' : `${Math.round(value)}%`}</dd>
              </div>

              <Progress
                aria-label={`${label}, percent of daily value`}
                value={value === null ? 0 : Math.min(100, Math.max(0, value))}
                className="h-1.5 bg-muted"
              />
            </div>
          )
        })}
      </dl>

      <p className="mt-4 text-xs leading-[1.5] text-ink-faint">
        Percent of daily value, as recorded in the Food.com dataset.
      </p>
    </section>
  )
}
