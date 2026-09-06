import { useQuery } from '@tanstack/react-query'

import { getMe } from '@/api/users'
import { hasToken } from '@/lib/auth'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The signed-in user. Disabled without a token so a signed-out visitor never
 * fires a request that is certain to 401, and never retried: a 401 here is
 * handled once by the response interceptor.
 */
export function useMe() {
  return useQuery({
    queryKey: queryKeys.me(),
    queryFn: getMe,
    enabled: hasToken(),
    retry: false,
  })
}
