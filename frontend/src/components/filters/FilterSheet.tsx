import { SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import {
  EMPTY_FILTERS,
  serializeFilters,
  type RecommendationFilters,
} from '@/lib/filters'

import { FilterFields } from './FilterFields'

interface FilterSheetProps {
  value: RecommendationFilters
  onApply: (value: RecommendationFilters) => void
  /** How many filters are currently active, shown on the trigger. */
  activeCount: number
}

interface FilterSheetBodyProps {
  value: RecommendationFilters
  onApply: (value: RecommendationFilters) => void
  onClose: () => void
}

function FilterSheetBody({ value, onApply, onClose }: FilterSheetBodyProps) {
  const [draft, setDraft] = useState(value)

  return (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-4">
        <FilterFields value={draft} onChange={setDraft} layout="sheet" />
      </div>

      <SheetFooter className="flex-row gap-3 border-t border-border px-5 py-4">
        <Button
          variant="ghost"
          className="h-12 flex-1 rounded-xl text-sm font-semibold text-muted-foreground"
          onClick={() => {
            setDraft(EMPTY_FILTERS)
            onApply(EMPTY_FILTERS)
            onClose()
          }}
        >
          Reset
        </Button>

        <Button
          className="h-12 flex-1 rounded-xl text-sm font-bold"
          onClick={() => {
            onApply(draft)
            onClose()
          }}
        >
          Apply
        </Button>
      </SheetFooter>
    </>
  )
}

/** The same four fields as the desktop bar, in a bottom sheet below `md`. */
export function FilterSheet({ value, onApply, activeCount }: FilterSheetProps) {
  const [open, setOpen] = useState(false)
  const applied = serializeFilters(value).toString()

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          className="mb-3.5 h-11 w-full justify-center gap-2 rounded-xl text-sm font-bold md:hidden"
        >
          <SlidersHorizontal className="size-[17px]" />
          Filters{activeCount > 0 ? ` (${activeCount})` : null}
        </Button>
      </SheetTrigger>

      <SheetContent
        side="bottom"
        className="max-h-[85dvh] rounded-t-3xl bg-background p-0"
      >
        <SheetHeader className="px-5 pt-5 pb-2">
          <SheetTitle className="text-xl font-extrabold tracking-[-0.03em]">
            Filters
          </SheetTitle>
          <SheetDescription>
            Narrow the recommendations down to what you can actually cook
            tonight.
          </SheetDescription>
        </SheetHeader>

        {/* Keyed on the applied filters so reopening the sheet always starts
            from what is really in the URL. */}
        <FilterSheetBody
          key={applied}
          value={value}
          onApply={onApply}
          onClose={() => {
            setOpen(false)
          }}
        />
      </SheetContent>
    </Sheet>
  )
}
