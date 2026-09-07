import { Navigate, Outlet } from 'react-router-dom'

import { hasToken } from '@/lib/auth'

/**
 * Cheap first gate: no token, no page. Whether the token is still *valid* is
 * decided by the first request the page makes — a 401 is handled centrally by
 * the response interceptor.
 */
export function ProtectedRoute() {
  if (!hasToken()) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
