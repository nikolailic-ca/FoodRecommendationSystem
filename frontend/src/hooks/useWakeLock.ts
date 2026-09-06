import { useEffect, useRef } from 'react'

/**
 * Keeps the screen awake while `active` is true.
 *
 * The Screen Wake Lock API only exists in a secure context and only in some
 * browsers, and the lock is dropped by the browser whenever the tab is hidden —
 * so every call is guarded and the lock is re-requested when the tab comes
 * back. Failing to get one is not an error the user needs to hear about; the
 * screen simply dims as it normally would.
 */
export function useWakeLock(active: boolean): void {
  const sentinel = useRef<WakeLockSentinel | null>(null)

  useEffect(() => {
    if (!active) {
      return
    }

    let cancelled = false

    async function request() {
      if (!('wakeLock' in navigator)) {
        return
      }

      try {
        const lock = await navigator.wakeLock.request('screen')

        if (cancelled) {
          void lock.release().catch(() => undefined)

          return
        }

        sentinel.current = lock
      } catch {
        // Denied, unsupported, or the document was not visible. Nothing to do.
      }
    }

    function release() {
      const lock = sentinel.current
      sentinel.current = null

      if (lock) {
        try {
          void lock.release().catch(() => undefined)
        } catch {
          // Already released by the browser.
        }
      }
    }

    function handleVisibilityChange() {
      if (document.visibilityState === 'visible') {
        void request()
      } else {
        release()
      }
    }

    void request()
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      release()
    }
  }, [active])
}
