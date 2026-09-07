import { TriangleAlert } from 'lucide-react'

import { getErrorMessage } from '@/api/client'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ErrorStateProps {
  title?: string
  /** Either a ready sentence or the thrown error, which is turned into one. */
  error?: unknown
  description?: string
  onRetry?: () => void
  className?: string
}

/** Reusable failure block: what went wrong, and a way to try again. */
export function ErrorState({
  title = 'Something went wrong',
  error,
  description,
  onRetry,
  className,
}: ErrorStateProps) {
  const message =
    description ?? (error === undefined ? undefined : getErrorMessage(error))

  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-3xl border border-black/5 bg-card px-6 py-12 text-center',
        className,
      )}
    >
      <span className="flex size-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <TriangleAlert className="size-5" />
      </span>

      <div className="space-y-1">
        <p className="text-base font-bold tracking-tight">{title}</p>
        {message ? (
          <p className="max-w-md text-sm text-muted-foreground">{message}</p>
        ) : null}
      </div>

      {onRetry ? (
        <Button variant="outline" size="lg" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  )
}
