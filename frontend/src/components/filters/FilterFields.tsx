import { Search } from 'lucide-react'
import { useId, useState } from 'react'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useIngredientSuggestions,
  useTagSuggestions,
} from '@/hooks/useSuggestions'
import {
  MAX_MINUTES_OPTIONS,
  maxMinutesLabel,
  type RecommendationFilters,
} from '@/lib/filters'
import { cn } from '@/lib/utils'

import { SuggestCombobox } from './SuggestCombobox'

/** Radix forbids an empty option value, so "no limit" needs a name. */
const ANY_TIME = 'any'

interface FilterFieldsProps {
  value: RecommendationFilters
  onChange: (value: RecommendationFilters) => void
  /** `bar` lays the four fields out in a row, `sheet` stacks them. */
  layout: 'bar' | 'sheet'
  /** Submitting the search field applies the filters straight away. */
  onSubmit?: () => void
}

const FIELD =
  'h-11 rounded-xl border border-border bg-background text-sm font-medium'

/**
 * The four filter controls, shared by the desktop bar and the mobile sheet.
 *
 * They edit a draft copy of the filters; committing that draft to the URL is
 * the caller's job, which is what lets the sheet hold unapplied changes until
 * its Apply button is pressed.
 */
export function FilterFields({
  value,
  onChange,
  layout,
  onSubmit,
}: FilterFieldsProps) {
  // The desktop bar and the mobile sheet are both mounted at all times — the
  // bar is only hidden with CSS — so a fixed id would have the sheet's label
  // point at the invisible input in the bar.
  const searchId = useId()

  const [ingredientQuery, setIngredientQuery] = useState('')
  const [tagQuery, setTagQuery] = useState('')

  const ingredients = useIngredientSuggestions(ingredientQuery)
  const tags = useTagSuggestions(tagQuery)

  const isBar = layout === 'bar'

  return (
    <div
      className={cn(
        isBar ? 'flex flex-1 items-center gap-3' : 'flex flex-col gap-4',
      )}
    >
      <div className={isBar ? 'flex-1' : 'w-full'}>
        {!isBar ? (
          <label
            htmlFor={searchId}
            className="mb-1.5 block text-[13px] font-bold"
          >
            Search
          </label>
        ) : null}

        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-[17px] -translate-y-1/2 text-muted-foreground" />

          <input
            id={searchId}
            type="search"
            value={value.query}
            placeholder="Search recipes"
            onChange={(event) => {
              onChange({ ...value, query: event.target.value })
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                onSubmit?.()
              }
            }}
            className={cn(
              FIELD,
              'w-full pr-3 pl-10 font-semibold outline-none placeholder:font-medium placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50',
            )}
          />
        </div>
      </div>

      <div className={isBar ? 'w-[150px]' : 'w-full'}>
        {!isBar ? (
          <span className="mb-1.5 block text-[13px] font-bold">
            Maximum time
          </span>
        ) : null}

        <Select
          value={
            value.maxMinutes === null ? ANY_TIME : String(value.maxMinutes)
          }
          onValueChange={(next) => {
            onChange({
              ...value,
              maxMinutes: next === ANY_TIME ? null : Number.parseInt(next, 10),
            })
          }}
        >
          <SelectTrigger
            aria-label="Maximum cooking time"
            className={cn(FIELD, 'w-full px-3 data-[size=default]:h-11')}
          >
            <SelectValue />
          </SelectTrigger>

          <SelectContent position="popper">
            <SelectItem value={ANY_TIME}>Any time</SelectItem>
            {MAX_MINUTES_OPTIONS.map((minutes) => (
              <SelectItem key={minutes} value={String(minutes)}>
                {maxMinutesLabel(minutes)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className={isBar ? 'w-[220px]' : 'w-full'}>
        {!isBar ? (
          <span className="mb-1.5 block text-[13px] font-bold">
            Ingredients
          </span>
        ) : null}

        <SuggestCombobox
          label="Ingredients"
          placeholder="Search ingredients"
          values={value.ingredients}
          onChange={(next) => {
            onChange({ ...value, ingredients: next })
          }}
          query={ingredientQuery}
          onQueryChange={setIngredientQuery}
          suggestions={ingredients.data ?? []}
          isLoading={ingredients.isFetching}
        />
      </div>

      <div className={isBar ? 'w-[190px]' : 'w-full'}>
        {!isBar ? (
          <span className="mb-1.5 block text-[13px] font-bold">Tags</span>
        ) : null}

        <SuggestCombobox
          label="Tags"
          placeholder="Search tags"
          values={value.tags}
          onChange={(next) => {
            onChange({ ...value, tags: next })
          }}
          query={tagQuery}
          onQueryChange={setTagQuery}
          suggestions={tags.data ?? []}
          isLoading={tags.isFetching}
        />
      </div>
    </div>
  )
}
