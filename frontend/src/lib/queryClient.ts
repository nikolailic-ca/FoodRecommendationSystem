import { QueryClient } from '@tanstack/react-query'

/**
 * One client for the whole app. Recipes and recommendations change rarely, so a
 * minute of freshness avoids refetching the grid every time a component
 * remounts, and window focus refetching is off because it would reshuffle the
 * recommendation grid while the user is reading it.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
