import type { RecommendationParams } from '@/api/types'

/**
 * The recommendation filters, mirrored into the URL as
 * `?q=&max=&ing=a,b&tags=x,y` so a filtered grid can be linked and reloaded.
 */
export interface RecommendationFilters {
  /** Free text matched against the recipe name. */
  query: string
  /** Upper bound on cooking time, in minutes. */
  maxMinutes: number | null
  ingredients: string[]
  tags: string[]
}

export const EMPTY_FILTERS: RecommendationFilters = {
  query: '',
  maxMinutes: null,
  ingredients: [],
  tags: [],
}

function normalizeList(values: string[]): string[] {
  const seen = new Set<string>()

  for (const value of values) {
    const cleaned = value.trim().toLowerCase()

    if (cleaned !== '') {
      seen.add(cleaned)
    }
  }

  // Sorting makes the query key independent of the order chips were added in,
  // so re-adding the same set of filters hits the cache instead of refetching.
  return [...seen].sort()
}

function parseList(value: string | null): string[] {
  return value === null ? [] : normalizeList(value.split(','))
}

function parseMaxMinutes(value: string | null): number | null {
  if (value === null) {
    return null
  }

  const parsed = Number.parseInt(value, 10)

  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

/** Canonical form: trimmed text, lowercase, de-duplicated and sorted lists. */
export function normalizeFilters(
  filters: RecommendationFilters,
): RecommendationFilters {
  return {
    query: filters.query.trim(),
    maxMinutes:
      filters.maxMinutes !== null && filters.maxMinutes > 0
        ? Math.round(filters.maxMinutes)
        : null,
    ingredients: normalizeList(filters.ingredients),
    tags: normalizeList(filters.tags),
  }
}

export function parseFilters(params: URLSearchParams): RecommendationFilters {
  return normalizeFilters({
    query: params.get('q') ?? '',
    maxMinutes: parseMaxMinutes(params.get('max')),
    ingredients: parseList(params.get('ing')),
    tags: parseList(params.get('tags')),
  })
}

export function serializeFilters(
  filters: RecommendationFilters,
): URLSearchParams {
  const normalized = normalizeFilters(filters)
  const params = new URLSearchParams()

  if (normalized.query !== '') {
    params.set('q', normalized.query)
  }

  if (normalized.maxMinutes !== null) {
    params.set('max', String(normalized.maxMinutes))
  }

  if (normalized.ingredients.length > 0) {
    params.set('ing', normalized.ingredients.join(','))
  }

  if (normalized.tags.length > 0) {
    params.set('tags', normalized.tags.join(','))
  }

  return params
}

/** The rungs offered by the max-cooking-time select, in minutes. */
export const MAX_MINUTES_OPTIONS = [15, 30, 45, 60, 120] as const

/** `30` -> `"Under 30 min"`, `120` -> `"Under 2 h"`. */
export function maxMinutesLabel(minutes: number): string {
  if (minutes < 60) {
    return `Under ${minutes} min`
  }

  const hours = minutes / 60

  return `Under ${hours} h`
}

/** `/home?tags=one-pot` — the target of every clickable tag chip. */
export function tagFilterHref(tag: string): string {
  const params = serializeFilters({ ...EMPTY_FILTERS, tags: [tag] })

  return `/home?${params.toString()}`
}

export function hasActiveFilters(filters: RecommendationFilters): boolean {
  const normalized = normalizeFilters(filters)

  return (
    normalized.query !== '' ||
    normalized.maxMinutes !== null ||
    normalized.ingredients.length > 0 ||
    normalized.tags.length > 0
  )
}

/** Maps the UI shape onto the query string `GET /recommendations/me` expects. */
export function toRecommendationParams(
  filters: RecommendationFilters,
): RecommendationParams {
  const normalized = normalizeFilters(filters)
  const params: RecommendationParams = {}

  if (normalized.query !== '') {
    params.name = normalized.query
  }

  if (normalized.maxMinutes !== null) {
    params.max_minutes = normalized.maxMinutes
  }

  if (normalized.ingredients.length > 0) {
    params.ingredients = normalized.ingredients.join(',')
  }

  if (normalized.tags.length > 0) {
    params.tags = normalized.tags.join(',')
  }

  return params
}
