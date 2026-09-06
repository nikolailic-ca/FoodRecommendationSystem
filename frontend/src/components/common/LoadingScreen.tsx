import { Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

interface LoadingScreenProps {
  label?: string
  /** Fills the viewport instead of the space it is given. */
  fullscreen?: boolean
  className?: string
}

/** Shown while a route decides what to render. */
export function LoadingScreen({
  label = 'Loading…',
  fullscreen = true,
  className,
}: LoadingScreenProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex flex-col items-center justify-center gap-3',
        fullscreen ? 'min-h-dvh' : 'min-h-60 py-16',
        className,
      )}
    >
      <Loader2 className="size-6 animate-spin text-primary" />
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
    </div>
  )
}
