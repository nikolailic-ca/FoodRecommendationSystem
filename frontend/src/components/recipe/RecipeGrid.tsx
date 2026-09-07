import type { ReactNode } from 'react'

import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface RecipeGridProps {
  children: ReactNode
  className?: string
}

/** One to four columns, the same everywhere cards are listed. */
export function RecipeGrid({ children, className }: RecipeGridProps) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
        className,
      )}
    >
      {children}
    </div>
  )
}

/**
 * Placeholder with the card's exact geometry — same image ratio, same padding,
 * same rows — so the grid does not jump when the real cards arrive.
 */
export function RecipeCardSkeleton() {
  return (
    <div className="flex flex-col overflow-hidden rounded-3xl border border-black/5 bg-card shadow-sm">
      <Skeleton className="aspect-[16/10] w-full rounded-none" />

      <div className="flex flex-col gap-2.5 p-4">
        <Skeleton className="h-[17px] w-full" />
        <Skeleton className="h-[17px] w-[62%]" />
        <Skeleton className="mt-1.5 h-[13px] w-[78%]" />
        <Skeleton className="h-[13px] w-[40%]" />

        <div className="mt-1 flex gap-1.5">
          <Skeleton className="h-[22px] w-[66px] rounded-full" />
          <Skeleton className="h-[22px] w-20 rounded-full" />
        </div>

        <Skeleton className="mt-1.5 h-3 w-[90%]" />
      </div>
    </div>
  )
}

interface RecipeGridSkeletonProps {
  count?: number
  className?: string
}

export function RecipeGridSkeleton({
  count = 8,
  className,
}: RecipeGridSkeletonProps) {
  return (
    <RecipeGrid className={className}>
      {Array.from({ length: count }, (_, index) => (
        <RecipeCardSkeleton key={index} />
      ))}
    </RecipeGrid>
  )
}
