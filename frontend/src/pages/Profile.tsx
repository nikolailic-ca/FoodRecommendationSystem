import { Bookmark, LogOut, Star } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingScreen } from '@/components/common/LoadingScreen'
import { RecipeCard } from '@/components/recipe/RecipeCard'
import { RecipeGrid, RecipeGridSkeleton } from '@/components/recipe/RecipeGrid'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useFavorites } from '@/hooks/useFavorites'
import { useLogout } from '@/hooks/useLogout'
import { useMe } from '@/hooks/useMe'
import { useDeleteRating, useRateRecipe, useRatings } from '@/hooks/useRatings'
import { formatDate } from '@/lib/format'

/** `GET /users/me/ratings` filters by *minimum* rating, so the labels say so. */
const MIN_RATING_OPTIONS = [
  { value: 'all', label: 'All ratings' },
  { value: '5', label: '5 stars only' },
  { value: '4', label: '4 stars and up' },
  { value: '3', label: '3 stars and up' },
  { value: '2', label: '2 stars and up' },
] as const

interface EmptyProps {
  title: string
  description: string
}

function Empty({ title, description }: EmptyProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-3xl border border-black/5 bg-card px-6 py-16 text-center">
      <p className="text-lg font-bold tracking-tight">{title}</p>
      <p className="max-w-md text-sm text-muted-foreground">{description}</p>
      <Button
        asChild
        variant="outline"
        className="mt-1 h-11 rounded-xl px-5 font-bold"
      >
        <Link to="/home">Browse recommendations</Link>
      </Button>
    </div>
  )
}

interface StatPillProps {
  icon: typeof Star
  value: string
  label: string
}

function StatPill({ icon: Icon, value, label }: StatPillProps) {
  return (
    <span className="flex items-center gap-2 rounded-full bg-secondary px-3.5 py-2 text-[13px] font-semibold text-ink-soft">
      <Icon className="size-4 text-muted-foreground" strokeWidth={1.9} />
      <span className="font-extrabold text-foreground">{value}</span>
      {label}
    </span>
  )
}

function RatedTab() {
  const [minRating, setMinRating] = useState<string>('all')
  const ratings = useRatings(minRating === 'all' ? undefined : Number(minRating))
  const rate = useRateRecipe()
  const removeRating = useDeleteRating()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium text-muted-foreground">
          {ratings.data
            ? `${ratings.data.length} ${ratings.data.length === 1 ? 'recipe' : 'recipes'}`
            : 'Loading…'}
        </p>

        <Select value={minRating} onValueChange={setMinRating}>
          <SelectTrigger
            aria-label="Filter by rating"
            className="h-11 w-[190px] rounded-xl border-border px-3 text-sm font-semibold data-[size=default]:h-11"
          >
            <SelectValue />
          </SelectTrigger>

          <SelectContent position="popper">
            {MIN_RATING_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {ratings.isPending ? <RecipeGridSkeleton count={4} /> : null}

      {ratings.isError ? (
        <ErrorState
          title="Could not load your ratings"
          error={ratings.error}
          onRetry={() => void ratings.refetch()}
        />
      ) : null}

      {ratings.data && ratings.data.length === 0 ? (
        <Empty
          title="Nothing rated yet"
          description="Rate a recipe and it shows up here, where you can change your mind at any time."
        />
      ) : null}

      {ratings.data && ratings.data.length > 0 ? (
        <RecipeGrid>
          {ratings.data.map((entry) => (
            <RecipeCard
              key={entry.recipe.id}
              recipe={entry.recipe}
              variant="rated"
              userRating={entry.rating}
              ratedAt={entry.updated_at}
              onRate={(value) => {
                rate.mutate({ recipeId: entry.recipe.id, rating: value })
              }}
              onRemoveRating={() => {
                removeRating.mutate(entry.recipe.id)
              }}
            />
          ))}
        </RecipeGrid>
      ) : null}
    </div>
  )
}

function FavoritesTab() {
  const favorites = useFavorites()

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm font-medium text-muted-foreground">
        {favorites.data
          ? `${favorites.data.length} ${favorites.data.length === 1 ? 'recipe' : 'recipes'} saved`
          : 'Loading…'}
      </p>

      {favorites.isPending ? <RecipeGridSkeleton count={4} /> : null}

      {favorites.isError ? (
        <ErrorState
          title="Could not load your favorites"
          error={favorites.error}
          onRetry={() => void favorites.refetch()}
        />
      ) : null}

      {favorites.data && favorites.data.length === 0 ? (
        <Empty
          title="Nothing saved yet"
          description="The bookmark on a card keeps a recipe here. It is separate from your rating and does not train the model."
        />
      ) : null}

      {favorites.data && favorites.data.length > 0 ? (
        <RecipeGrid>
          {favorites.data.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} variant="browse" />
          ))}
        </RecipeGrid>
      ) : null}
    </div>
  )
}

interface AccountTabProps {
  username: string
  email: string
  createdAt: string
  ratingsCount: number
}

function AccountTab({
  username,
  email,
  createdAt,
  ratingsCount,
}: AccountTabProps) {
  const logout = useLogout()

  const rows = [
    { label: 'Username', value: username },
    { label: 'Email', value: email },
    { label: 'Member since', value: formatDate(createdAt) },
    { label: 'Recipes rated', value: String(ratingsCount) },
  ]

  return (
    <div className="max-w-2xl">
      <section className="rounded-3xl border border-border bg-card p-7">
        <h2 className="mb-[18px] text-xl font-extrabold tracking-[-0.025em]">
          Account details
        </h2>

        <dl className="flex flex-col">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex items-center justify-between gap-4 border-b border-border py-3.5 last:border-b-0"
            >
              <dt className="text-sm font-semibold text-muted-foreground">
                {row.label}
              </dt>
              <dd className="text-[15px] font-semibold break-all">
                {row.value}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="mt-6 flex flex-col gap-3 rounded-3xl border border-border bg-card p-7 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[15px] font-bold">Log out</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Ends the session on this device and clears everything cached here.
          </p>
        </div>

        <Button
          variant="outline"
          className="h-11 shrink-0 gap-2 rounded-xl px-5 font-bold"
          onClick={logout}
        >
          <LogOut className="size-[17px]" />
          Log out
        </Button>
      </div>
    </div>
  )
}

/** The account: who you are, what you rated and what you saved. */
function Profile() {
  const me = useMe()
  const favorites = useFavorites()

  if (me.isPending) {
    return <LoadingScreen fullscreen={false} label="Loading your account…" />
  }

  if (me.isError) {
    return (
      <ErrorState
        title="Could not load your account"
        error={me.error}
        onRetry={() => void me.refetch()}
      />
    )
  }

  const initial = me.data.username.trim().charAt(0).toUpperCase() || '?'

  return (
    <>
      <header className="mb-8 flex flex-col gap-5 rounded-3xl border border-border bg-card p-7 sm:flex-row sm:items-center sm:gap-6">
        <span className="flex size-[72px] shrink-0 items-center justify-center rounded-full bg-accent text-[28px] font-extrabold text-accent-foreground">
          {initial}
        </span>

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-3xl leading-tight font-extrabold tracking-[-0.035em]">
            {me.data.username}
          </h1>
          <p className="mt-1 text-sm font-medium break-words text-muted-foreground">
            {me.data.email} · Member since {formatDate(me.data.created_at)}
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            <StatPill
              icon={Star}
              value={String(me.data.ratings_count)}
              label={me.data.ratings_count === 1 ? 'rating' : 'ratings'}
            />
            <StatPill
              icon={Bookmark}
              value={String(favorites.data?.length ?? 0)}
              label="saved"
            />
          </div>
        </div>
      </header>

      <Tabs defaultValue="rated" className="gap-6">
        <TabsList className="h-11 w-full max-w-[420px]">
          <TabsTrigger value="rated" className="text-sm font-semibold">
            Rated
          </TabsTrigger>
          <TabsTrigger value="favorites" className="text-sm font-semibold">
            Favorites
          </TabsTrigger>
          <TabsTrigger value="account" className="text-sm font-semibold">
            Account
          </TabsTrigger>
        </TabsList>

        <TabsContent value="rated">
          <RatedTab />
        </TabsContent>

        <TabsContent value="favorites">
          <FavoritesTab />
        </TabsContent>

        <TabsContent value="account">
          <AccountTab
            username={me.data.username}
            email={me.data.email}
            createdAt={me.data.created_at}
            ratingsCount={me.data.ratings_count}
          />
        </TabsContent>
      </Tabs>
    </>
  )
}

export default Profile
