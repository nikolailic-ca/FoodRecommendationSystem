import { useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingScreen } from '@/components/common/LoadingScreen'
import { useMe } from '@/hooks/useMe'

/**
 * Whether onboarding was already finished the first time this route saw the
 * account.
 *
 * Both guards decide on entry rather than on every render, because
 * `onboarding_completed` is derived from the rating count and therefore flips
 * mid-session: rating the fifth recipe would otherwise throw the user off the
 * onboarding screen before they can press Continue, and removing a rating on
 * the profile would throw them onto it. Storing the first answer during render
 * is React's own "adjust state when the input changes" pattern — the extra
 * render happens once, before anything is painted.
 */
function useEnteredWith(completed: boolean | undefined): boolean | undefined {
  const [enteredWith, setEnteredWith] = useState<boolean | undefined>(undefined)

  if (enteredWith === undefined && completed !== undefined) {
    setEnteredWith(completed)

    return completed
  }

  return enteredWith
}

/**
 * Guards `/onboarding`: only a user who has not finished it belongs there.
 * Anyone who already has goes straight to the recommendations.
 */
export function RequireOnboarding() {
  const { data: me, isPending, isError, error, refetch } = useMe()
  const enteredWith = useEnteredWith(me?.onboarding_completed)

  if (isPending) {
    return <LoadingScreen label="Loading your account…" />
  }

  if (isError) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-md items-center px-4">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    )
  }

  if (enteredWith ?? me.onboarding_completed) {
    return <Navigate to="/home" replace />
  }

  return <Outlet />
}

/**
 * Guards the main app: a user who has not rated anything yet is sent back to
 * onboarding, because there is nothing to recommend from.
 */
export function RequireOnboarded() {
  const { data: me, isPending, isError, error, refetch } = useMe()
  const enteredWith = useEnteredWith(me?.onboarding_completed)

  if (isPending) {
    return <LoadingScreen label="Loading your account…" />
  }

  if (isError) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-md items-center px-4">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    )
  }

  if ((enteredWith ?? me.onboarding_completed) === false) {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}
