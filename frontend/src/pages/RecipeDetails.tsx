import { Link, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingScreen } from '@/components/common/LoadingScreen'
import { PageHeader } from '@/components/layout/PageHeader'
import { useRecipe } from '@/hooks/useRecipe'
import { useSimilar } from '@/hooks/useSimilar'
import { formatCalories, formatDate, formatMinutes } from '@/lib/format'

function parseRecipeId(value: string | undefined): number | null {
  if (value === undefined) {
    return null
  }

  const parsed = Number.parseInt(value, 10)

  return Number.isInteger(parsed) ? parsed : null
}

/** Placeholder: renders the raw detail payload plus the similar-recipes list. */
function RecipeDetails() {
  const { recipeId } = useParams()
  const id = parseRecipeId(recipeId)

  const { data: recipe, error, isPending, isError, refetch } = useRecipe(id)
  const similar = useSimilar(id)

  if (id === null) {
    return <ErrorState title="Unknown recipe" description="Bad recipe id." />
  }

  if (isPending) {
    return <LoadingScreen fullscreen={false} />
  }

  if (isError) {
    return <ErrorState error={error} onRetry={() => void refetch()} />
  }

  return (
    <>
      <PageHeader
        eyebrow={`Recipe #${recipe.id}`}
        title={recipe.name}
        subtitle={`${formatMinutes(recipe.minutes)} · ${formatCalories(
          recipe.calories,
        )} · ${recipe.n_ingredients} ingredients · ${recipe.n_steps} steps · submitted ${formatDate(recipe.submitted)}`}
      />

      <div className="flex flex-col gap-4 text-sm">
        <p className="text-muted-foreground">
          your rating: {recipe.user_rating ?? '—'} · favorite:{' '}
          {String(recipe.is_favorite)} · average {recipe.avg_rating} over{' '}
          {recipe.rating_count} ratings
        </p>

        <p>{recipe.description}</p>

        <div>
          <h2 className="font-bold">Ingredients</h2>
          <ul className="list-disc pl-5 text-muted-foreground">
            {recipe.ingredients.map((ingredient) => (
              <li key={ingredient}>{ingredient}</li>
            ))}
          </ul>
        </div>

        <div>
          <h2 className="font-bold">Steps</h2>
          <ol className="list-decimal pl-5 text-muted-foreground">
            {recipe.steps.map((step, index) => (
              <li key={`${index}-${step.slice(0, 24)}`}>{step}</li>
            ))}
          </ol>
        </div>

        <div>
          <h2 className="font-bold">Nutrition</h2>
          <pre className="overflow-x-auto text-xs text-muted-foreground">
            {JSON.stringify(recipe.nutrition, null, 2)}
          </pre>
        </div>

        <div>
          <h2 className="font-bold">Similar recipes</h2>
          {similar.isError ? (
            <ErrorState
              error={similar.error}
              onRetry={() => void similar.refetch()}
            />
          ) : (
            <ul className="text-muted-foreground">
              {similar.data?.map(({ recipe: neighbour, similarity }) => (
                <li key={neighbour.id}>
                  <Link to={`/recipes/${neighbour.id}`}>{neighbour.name}</Link> ·{' '}
                  {similarity.toFixed(3)}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  )
}

export default RecipeDetails
