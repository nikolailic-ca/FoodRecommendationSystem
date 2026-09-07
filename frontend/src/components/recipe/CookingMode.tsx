import { Check, X } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useWakeLock } from '@/hooks/useWakeLock'
import { cn } from '@/lib/utils'

interface CookingModeProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  name: string
  ingredients: string[]
  steps: string[]
}

interface IngredientListProps {
  ingredients: string[]
  checked: Set<number>
  onToggle: (index: number) => void
}

function IngredientList({
  ingredients,
  checked,
  onToggle,
}: IngredientListProps) {
  return (
    <ul className="flex flex-col">
      {ingredients.map((ingredient, index) => (
        <li key={`${index}-${ingredient}`}>
          <label className="flex cursor-pointer items-center gap-3.5 border-b border-border py-3 text-[17px] font-medium last:border-b-0">
            <Checkbox
              className="size-5 shrink-0"
              checked={checked.has(index)}
              onCheckedChange={() => {
                onToggle(index)
              }}
            />
            <span
              className={cn(
                'transition-colors',
                checked.has(index) &&
                  'text-muted-foreground line-through decoration-muted-foreground',
              )}
            >
              {ingredient}
            </span>
          </label>
        </li>
      ))}
    </ul>
  )
}

interface StepListProps {
  steps: string[]
  done: Set<number>
  onToggle: (index: number) => void
}

function StepList({ steps, done, onToggle }: StepListProps) {
  return (
    <ol className="flex flex-col gap-3">
      {steps.map((step, index) => (
        <li key={`${index}-${step.slice(0, 24)}`}>
          <button
            type="button"
            aria-pressed={done.has(index)}
            onClick={() => {
              onToggle(index)
            }}
            className={cn(
              'flex w-full cursor-pointer items-start gap-4 rounded-2xl border p-4 text-left transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
              done.has(index)
                ? 'border-primary/30 bg-accent/60'
                : 'border-border hover:bg-muted/60',
            )}
          >
            <span
              className={cn(
                'flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-extrabold',
                done.has(index)
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-accent text-accent-foreground',
              )}
            >
              {done.has(index) ? <Check className="size-4" /> : index + 1}
            </span>

            <span
              className={cn(
                'pt-1 text-[17px] leading-[1.6]',
                done.has(index) && 'text-muted-foreground line-through',
              )}
            >
              {step}
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}

/**
 * The recipe, full screen and at kitchen distance.
 *
 * Ingredients tick off, steps tap through, and the screen is asked to stay
 * awake for as long as the dialog is open. Below `lg` the two lists share the
 * width through tabs; above it they sit side by side, so a laptop on the
 * counter shows everything at once.
 *
 * What has been ticked is keyed by list index and lives for as long as this
 * component is mounted, which makes it state *about one recipe*. Callers must
 * therefore mount one instance per recipe — `RecipeDetails` keys its whole page
 * on the recipe id — or the same indices carry over and strike through the
 * wrong lines.
 */
export function CookingMode({
  open,
  onOpenChange,
  name,
  ingredients,
  steps,
}: CookingModeProps) {
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const [done, setDone] = useState<Set<number>>(new Set())

  useWakeLock(open)

  function toggle(
    setter: (update: (previous: Set<number>) => Set<number>) => void,
  ) {
    return (index: number) => {
      setter((previous) => {
        const next = new Set(previous)

        if (next.has(index)) {
          next.delete(index)
        } else {
          next.add(index)
        }

        return next
      })
    }
  }

  const progress = steps.length === 0 ? 0 : (done.size / steps.length) * 100

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="top-0 left-0 flex h-dvh w-screen max-w-none translate-x-0 translate-y-0 flex-col gap-0 rounded-none bg-background p-0 ring-0 sm:max-w-none"
      >
        <header className="flex shrink-0 items-start gap-4 border-b border-border px-4 py-4 sm:px-8">
          <div className="min-w-0 flex-1">
            <DialogTitle className="truncate text-xl font-extrabold tracking-[-0.03em] capitalize sm:text-2xl">
              {name}
            </DialogTitle>
            <DialogDescription className="mt-1 text-[13px]">
              Ingredients and steps, sized for the kitchen. Your screen stays
              awake.
            </DialogDescription>
          </div>

          <div className="hidden w-56 shrink-0 flex-col gap-2 pt-1 sm:flex">
            <span className="text-[13px] font-bold">
              {done.size}/{steps.length} steps
            </span>
            <Progress
              aria-label="Steps completed"
              value={progress}
              className="h-1.5 bg-muted"
            />
          </div>

          <DialogClose asChild>
            <Button
              variant="outline"
              className="h-11 shrink-0 gap-2 rounded-xl px-4 text-sm font-bold"
            >
              <X className="size-[18px]" />
              <span className="hidden sm:inline">Close</span>
            </Button>
          </DialogClose>
        </header>

        <div className="flex shrink-0 flex-col gap-2 border-b border-border px-4 py-3 sm:hidden">
          <span className="text-[13px] font-bold">
            {done.size}/{steps.length} steps
          </span>
          <Progress
            aria-label="Steps completed"
            value={progress}
            className="h-1.5 bg-muted"
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-8">
          <Tabs defaultValue="steps" className="lg:hidden">
            <TabsList className="h-11 w-full">
              <TabsTrigger value="ingredients" className="text-sm font-semibold">
                Ingredients
              </TabsTrigger>
              <TabsTrigger value="steps" className="text-sm font-semibold">
                Steps
              </TabsTrigger>
            </TabsList>

            <TabsContent value="ingredients" className="pt-4">
              <IngredientList
                ingredients={ingredients}
                checked={checked}
                onToggle={toggle(setChecked)}
              />
            </TabsContent>

            <TabsContent value="steps" className="pt-4">
              <StepList steps={steps} done={done} onToggle={toggle(setDone)} />
            </TabsContent>
          </Tabs>

          <div className="mx-auto hidden max-w-7xl grid-cols-[380px_minmax(0,1fr)] gap-12 lg:grid">
            <section>
              <h2 className="mb-4 text-xl font-extrabold tracking-[-0.025em]">
                Ingredients
              </h2>
              <IngredientList
                ingredients={ingredients}
                checked={checked}
                onToggle={toggle(setChecked)}
              />
            </section>

            <section>
              <h2 className="mb-4 text-xl font-extrabold tracking-[-0.025em]">
                Steps
              </h2>
              <StepList steps={steps} done={done} onToggle={toggle(setDone)} />
            </section>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
