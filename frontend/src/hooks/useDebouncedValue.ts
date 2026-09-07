import { useEffect, useState } from 'react'

/**
 * Trails `value` by `delay` milliseconds.
 *
 * Keeping the debounce in its own hook, rather than in an effect that fetches
 * and stores results, means the query hooks stay declarative: the debounced
 * value simply becomes part of a query key.
 */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebounced(value)
    }, delay)

    return () => {
      clearTimeout(timeout)
    }
  }, [value, delay])

  return debounced
}
