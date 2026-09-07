import { useQuery } from '@tanstack/react-query'

import { getOnboardingRecipes } from '@/api/recommendations'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The popular recipes a new account rates during onboarding.
 *
 * A deck that arrived is stable for the whole session, otherwise it would
 * shuffle under the user between ratings. An *empty* deck is a different thing:
 * the backend builds it lazily and stores `cards or None`, so an empty answer
 * means "not ready yet, ask again" rather than "there are none". Caching that
 * forever would strand the account on a blank onboarding screen for the rest of
 * the session, so an empty result stays stale and refetchable.
 */
export function useOnboardingRecipes() {
  return useQuery({
    queryKey: queryKeys.onboardingRecipes(),
    queryFn: getOnboardingRecipes,
    staleTime: (query) =>
      query.state.data && query.state.data.length > 0 ? Infinity : 0,
  })
}
