/**
 * How many ratings the onboarding copy asks for.
 *
 * Display only. The real threshold is `settings.onboarding_min_ratings` on the
 * server, and `GET /users/me` already reports the verdict as
 * `onboarding_completed` — that flag is what both the route guard and the
 * Continue button go by, so nothing gates on this number.
 */
export const MIN_ONBOARDING_RATINGS = 5
