import { Navigate, Outlet } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingScreen } from '@/components/common/LoadingScreen'
import { useMe } from '@/hooks/useMe'

/**
 * Guards `/onboarding`: only a user who has not finished it belongs there.
 * Anyone who already has goes straight to the recommendations.
 */
export function RequireOnboarding() {
  const { data: me, isPending, isError, error, refetch } = useMe()

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

  if (me.onboarding_completed) {
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

  if (me.onboarding_completed === false) {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}
