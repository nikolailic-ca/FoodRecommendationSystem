import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

import { clearToken } from '@/lib/auth'

/** Drops the token, throws away every cached response and returns to /login. */
export function useLogout() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  return useCallback(() => {
    clearToken()
    queryClient.clear()
    navigate('/login', { replace: true })
  }, [navigate, queryClient])
}
