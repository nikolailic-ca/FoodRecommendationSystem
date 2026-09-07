import { ChefHat, LogOut, Sparkles, User } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useLogout } from '@/hooks/useLogout'
import { useMe } from '@/hooks/useMe'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/home', label: 'Home', icon: Sparkles },
  { to: '/profile', label: 'Profile', icon: User },
] as const

function initialOf(username: string | undefined): string {
  return username?.trim().charAt(0).toUpperCase() || '?'
}

/** Sticky product header: brand mark, nav pills, and the account menu. */
export function AppHeader() {
  const { data: me } = useMe()
  const logout = useLogout()

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-[68px] max-w-7xl items-center gap-4 px-4 sm:gap-7 sm:px-6 lg:px-8">
        <NavLink to="/home" className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-[10px] bg-primary text-primary-foreground">
            <ChefHat className="size-[18px]" />
          </span>
          <span className="text-lg font-extrabold tracking-[-0.03em]">
            FoodRec
          </span>
        </NavLink>

        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              // Below `sm` the labels are dropped and the glyph carries the nav,
              // which is what keeps the brand and the account menu on one line.
              aria-label={item.label}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-full px-3 py-2 text-sm transition-colors sm:px-3.5',
                  isActive
                    ? 'bg-accent font-bold text-accent-foreground'
                    : 'font-semibold text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <item.icon className="size-[17px] sm:hidden" strokeWidth={1.9} />
              <span className="hidden sm:inline">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="grow" />

        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-3 rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
            <span className="hidden text-sm font-semibold sm:inline">
              {me?.username ?? '…'}
            </span>
            <span className="flex size-9 items-center justify-center rounded-full bg-accent text-[15px] font-extrabold text-accent-foreground">
              {initialOf(me?.username)}
            </span>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" className="min-w-44">
            <DropdownMenuItem onSelect={logout}>
              <LogOut />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
