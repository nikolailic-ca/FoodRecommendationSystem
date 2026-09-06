import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  EMPTY_FILTERS,
  serializeFilters,
  type RecommendationFilters,
} from '@/lib/filters'

import { FilterFields } from './FilterFields'

interface FilterBarProps {
  /** The filters currently in the URL. */
  value: RecommendationFilters
  onApply: (value: RecommendationFilters) => void
}

function FilterBarForm({ value, onApply }: FilterBarProps) {
  const [draft, setDraft] = useState(value)

  function apply() {
    onApply(draft)
  }

  return (
    <form
      className="mb-3.5 hidden items-center gap-3 rounded-[20px] border border-border bg-card p-3.5 md:flex"
      onSubmit={(event) => {
        event.preventDefault()
        apply()
      }}
    >
      <FilterFields
        value={draft}
        onChange={setDraft}
        layout="bar"
        onSubmit={apply}
      />

      <Button
        type="submit"
        className="h-11 shrink-0 rounded-xl px-[22px] text-sm font-bold shadow-[0_2px_8px_rgba(63,163,77,0.28)]"
      >
        Apply
      </Button>

      <Button
        type="button"
        variant="ghost"
        className="h-11 shrink-0 rounded-xl px-4 text-sm font-semibold text-muted-foreground"
        onClick={() => {
          setDraft(EMPTY_FILTERS)
          onApply(EMPTY_FILTERS)
        }}
      >
        Reset
      </Button>
    </form>
  )
}

/**
 * The desktop filter row.
 *
 * Edits are held locally until Apply, so typing in the search box does not fire
 * a request per keystroke; the URL — and with it the query key — only changes
 * on submit. Keying the form on the applied filters resets that draft whenever
 * the URL changes from somewhere else, such as a tag chip on a card.
 */
export function FilterBar({ value, onApply }: FilterBarProps) {
  const applied = serializeFilters(value).toString()

  return <FilterBarForm key={applied} value={value} onApply={onApply} />
}
