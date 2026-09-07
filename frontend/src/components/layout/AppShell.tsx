import { useEffect } from 'react'
import { Outlet, useLocation, useNavigationType } from 'react-router-dom'

import { AppHeader } from './AppHeader'

/** The frame every signed-in page renders inside. */
export function AppShell() {
  const { pathname } = useLocation()
  const navigationType = useNavigationType()

  // A new page starts at the top; going back keeps whatever the browser
  // restored, so returning from a recipe lands where the grid was left.
  useEffect(() => {
    if (navigationType !== 'POP') {
      window.scrollTo(0, 0)
    }
  }, [pathname, navigationType])

  return (
    <div className="min-h-dvh bg-background">
      <AppHeader />

      <main className="mx-auto max-w-7xl px-4 pt-10 pb-14 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
