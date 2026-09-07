import { Check, Eye, EyeOff } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'
import { useState } from 'react'

import { cn } from '@/lib/utils'

interface AuthFieldProps extends Omit<ComponentProps<'input'>, 'className'> {
  id: string
  label: string
  /** Drawn inside the field, on the leading edge. */
  icon: ReactNode
  /** Adds the show/hide toggle and starts the field masked. */
  password?: boolean
  hint?: string
  /** Shows a green tick on the trailing edge, e.g. once two passwords match. */
  valid?: boolean
}

/**
 * One labelled field on the auth screens: 48px tall, rounded, with a muted
 * glyph on the left and — for passwords — an eye that reveals what was typed.
 */
export function AuthField({
  id,
  label,
  icon,
  password = false,
  hint,
  valid = false,
  ...props
}: AuthFieldProps) {
  const [revealed, setRevealed] = useState(false)

  return (
    <div className="flex flex-col gap-[7px]">
      <label htmlFor={id} className="text-[13px] font-bold tracking-[-0.01em]">
        {label}
      </label>

      <div
        className={cn(
          'flex h-12 items-center gap-2.5 rounded-[14px] border border-border bg-background px-[15px]',
          'focus-within:border-primary focus-within:ring-3 focus-within:ring-primary/15',
        )}
      >
        <span className="flex shrink-0 text-ink-faint">{icon}</span>

        <input
          id={id}
          type={password && !revealed ? 'password' : props.type ?? 'text'}
          className="h-full w-full min-w-0 bg-transparent text-[15px] font-semibold outline-none placeholder:font-medium placeholder:text-muted-foreground"
          {...props}
        />

        {valid ? (
          <Check className="size-[17px] shrink-0 text-primary" strokeWidth={2.4} />
        ) : null}

        {password ? (
          <button
            type="button"
            onClick={() => {
              setRevealed((previous) => !previous)
            }}
            aria-label={revealed ? 'Hide password' : 'Show password'}
            className="flex shrink-0 cursor-pointer rounded-md p-1 text-ink-faint transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {revealed ? (
              <EyeOff className="size-[17px]" strokeWidth={1.9} />
            ) : (
              <Eye className="size-[17px]" strokeWidth={1.9} />
            )}
          </button>
        ) : null}
      </div>

      {hint ? (
        <span className="text-[12.5px] font-medium text-muted-foreground">
          {hint}
        </span>
      ) : null}
    </div>
  )
}
