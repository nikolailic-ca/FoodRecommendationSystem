import { Link } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingScreen } from '@/components/common/LoadingScreen'
import { PageHeader } from '@/components/layout/PageHeader'
import { useFavorites } from '@/hooks/useFavorites'
import { useMe } from '@/hooks/useMe'
import { useRatings } from '@/hooks/useRatings'
import { formatDate } from '@/lib/format'

/** Placeholder: the account, its ratings and its favourites, unstyled. */
function Profile() {
  const me = useMe()
  const ratings = useRatings()
  const favorites = useFavorites()

  if (me.isPending) {
    return <LoadingScreen fullscreen={false} />
  }

  if (me.isError) {
    return <ErrorState error={me.error} onRetry={() => void me.refetch()} />
  }

  return (
    <>
      <PageHeader
        eyebrow="Your account"
        title={me.data.username}
        subtitle={`${me.data.email} · joined ${formatDate(me.data.created_at)} · ${me.data.ratings_count} ratings · onboarding ${String(me.data.onboarding_completed)}`}
      />

      <section className="mb-8 text-sm">
        <h2 className="mb-2 font-bold">Ratings</h2>
        {ratings.isPending ? <LoadingScreen fullscreen={false} /> : null}
        {ratings.isError ? (
          <ErrorState
            error={ratings.error}
            onRetry={() => void ratings.refetch()}
          />
        ) : null}
        <ul className="text-muted-foreground">
          {ratings.data?.map((entry) => (
            <li key={entry.recipe.id}>
              <Link to={`/recipes/${entry.recipe.id}`}>{entry.recipe.name}</Link>{' '}
              · {entry.rating}/5 · {formatDate(entry.updated_at)}
            </li>
          ))}
        </ul>
      </section>

      <section className="text-sm">
        <h2 className="mb-2 font-bold">Favorites</h2>
        {favorites.isPending ? <LoadingScreen fullscreen={false} /> : null}
        {favorites.isError ? (
          <ErrorState
            error={favorites.error}
            onRetry={() => void favorites.refetch()}
          />
        ) : null}
        <ul className="text-muted-foreground">
          {favorites.data?.map((recipe) => (
            <li key={recipe.id}>
              <Link to={`/recipes/${recipe.id}`}>{recipe.name}</Link>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}

export default Profile
