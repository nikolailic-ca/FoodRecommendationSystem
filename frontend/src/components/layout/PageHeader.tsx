import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface PageHeaderProps {
  /** Small uppercase kicker above the title. */
  eyebrow?: string
  title: string
  subtitle?: string
  /** Rendered on the trailing edge, baseline-aligned with the title. */
  actions?: ReactNode
  className?: string
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between',
        className,
      )}
    >
      <div className="flex flex-col gap-1.5">
        {eyebrow ? (
          <span className="text-xs font-extrabold tracking-[0.12em] text-primary uppercase">
            {eyebrow}
          </span>
        ) : null}

        <h1 className="text-3xl leading-tight font-extrabold tracking-[-0.035em] text-balance sm:text-[38px]">
          {title}
        </h1>

        {subtitle ? (
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
      </div>

      {actions ? (
        <div className="flex items-center gap-2 sm:pb-1">{actions}</div>
      ) : null}
    </div>
  )
}
