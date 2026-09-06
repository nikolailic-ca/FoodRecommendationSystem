import { Outlet } from 'react-router-dom'

import { AppHeader } from './AppHeader'

/** The frame every signed-in page renders inside. */
export function AppShell() {
  return (
    <div className="min-h-dvh bg-background">
      <AppHeader />

      <main className="mx-auto max-w-7xl px-4 pt-10 pb-14 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
