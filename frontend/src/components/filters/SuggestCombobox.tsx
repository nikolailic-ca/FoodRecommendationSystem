import { Check, ChevronDown, Loader2, X } from 'lucide-react'
import { useState } from 'react'

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

interface SuggestComboboxProps {
  /** Shown on the closed trigger, e.g. "Ingredients". */
  label: string
  placeholder: string
  values: string[]
  onChange: (values: string[]) => void
  /** The text in the search box, owned by the parent so it can drive the query. */
  query: string
  onQueryChange: (query: string) => void
  suggestions: string[]
  isLoading?: boolean
  /** Shown while the query is too short for the server to answer. */
  hint?: string
  className?: string
}

/**
 * Multi-select over a server-side suggestion list.
 *
 * `shouldFilter` is off: the matching happens in Postgres, and cmdk filtering
 * the ten rows it already narrowed would only hide results whose spelling does
 * not literally contain what was typed.
 */
export function SuggestCombobox({
  label,
  placeholder,
  values,
  onChange,
  query,
  onQueryChange,
  suggestions,
  isLoading = false,
  hint = 'Type at least two letters.',
  className,
}: SuggestComboboxProps) {
  const [open, setOpen] = useState(false)

  function toggleValue(value: string) {
    const normalized = value.trim().toLowerCase()

    onChange(
      values.includes(normalized)
        ? values.filter((item) => item !== normalized)
        : [...values, normalized],
    )
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={cn(
          'flex h-11 w-full cursor-pointer items-center justify-between gap-2 rounded-xl border border-border bg-background px-3 text-sm font-medium transition-colors outline-none hover:bg-muted/60 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50',
          className,
        )}
      >
        <span
          className={cn(
            'truncate',
            values.length > 0 ? 'font-semibold text-foreground' : 'text-muted-foreground',
          )}
        >
          {values.length === 0 ? label : `${label} · ${values.length}`}
        </span>
        <ChevronDown className="size-[17px] shrink-0 text-muted-foreground" />
      </PopoverTrigger>

      <PopoverContent
        align="start"
        className="w-[min(20rem,calc(100vw-2rem))] p-0"
      >
        <Command shouldFilter={false}>
          <div className="border-b border-border p-2">
            <input
              value={query}
              onChange={(event) => {
                onQueryChange(event.target.value)
              }}
              placeholder={placeholder}
              autoComplete="off"
              className="h-9 w-full rounded-lg border border-border bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </div>

          {values.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 border-b border-border p-2">
              {values.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => {
                    toggleValue(value)
                  }}
                  className="flex cursor-pointer items-center gap-1.5 rounded-full bg-accent py-1 pr-2 pl-2.5 text-xs font-semibold text-accent-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  {value}
                  <X className="size-3.5" />
                </button>
              ))}
            </div>
          ) : null}

          <CommandList>
            {isLoading ? (
              <div className="flex items-center gap-2 px-3 py-6 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Searching…
              </div>
            ) : (
              <>
                <CommandEmpty className="px-3 py-6 text-sm text-muted-foreground">
                  {query.trim().length < 2 ? hint : 'Nothing matches.'}
                </CommandEmpty>

                <CommandGroup>
                  {suggestions.map((suggestion) => (
                    <CommandItem
                      key={suggestion}
                      value={suggestion}
                      onSelect={() => {
                        toggleValue(suggestion)
                      }}
                      className="cursor-pointer"
                    >
                      <span
                        className={cn(
                          'flex size-4 shrink-0 items-center justify-center rounded border',
                          values.includes(suggestion)
                            ? 'border-primary bg-primary text-primary-foreground'
                            : 'border-border',
                        )}
                      >
                        {values.includes(suggestion) ? (
                          <Check className="size-3" />
                        ) : null}
                      </span>
                      {suggestion}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
