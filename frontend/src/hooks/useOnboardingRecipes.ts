import { useQuery } from '@tanstack/react-query'

import { getOnboardingRecipes } from '@/api/recommendations'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The popular recipes a new account rates during onboarding. The set is stable
 * for the whole session, otherwise the deck would shuffle under the user
 * between ratings.
 */
export function useOnboardingRecipes() {
  return useQuery({
    queryKey: queryKeys.onboardingRecipes(),
    queryFn: getOnboardingRecipes,
    staleTime: Infinity,
  })
}
