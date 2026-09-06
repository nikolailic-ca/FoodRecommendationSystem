const EMPTY = '—'

/** `95` -> `"1 h 35 min"`, `35` -> `"35 min"`, `120` -> `"2 h"`. */
export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || !Number.isFinite(minutes)) {
    return EMPTY
  }

  const total = Math.max(0, Math.round(minutes))

  if (total < 60) {
    return `${total} min`
  }

  const hours = Math.floor(total / 60)
  const rest = total % 60

  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`
}

function trimDecimal(value: number): string {
  const rounded = Math.round(value * 10) / 10

  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
}

/** `890` -> `"890"`, `1200` -> `"1.2k"`, `2_400_000` -> `"2.4M"`. */
export function formatCount(count: number | null | undefined): string {
  if (count === null || count === undefined || !Number.isFinite(count)) {
    return EMPTY
  }

  const value = Math.max(0, Math.round(count))

  if (value < 1_000) {
    return String(value)
  }

  if (value < 1_000_000) {
    return `${trimDecimal(value / 1_000)}k`
  }

  return `${trimDecimal(value / 1_000_000)}M`
}

/** `486.2` -> `"486 kcal"`. */
export function formatCalories(calories: number | null | undefined): string {
  if (
    calories === null ||
    calories === undefined ||
    !Number.isFinite(calories)
  ) {
    return EMPTY
  }

  return `${Math.round(calories)} kcal`
}

const dateFormatter = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

/** ISO date from the API -> `"12 Mar 2018"`. */
export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return EMPTY
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return EMPTY
  }

  return dateFormatter.format(date)
}
