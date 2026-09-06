import { Navigate, Outlet } from 'react-router-dom'

import { hasToken } from '@/lib/auth'

/** Keeps a signed-in user away from the login and register screens. */
export function PublicOnlyRoute() {
  if (hasToken()) {
    return <Navigate to="/home" replace />
  }

  return <Outlet />
}
