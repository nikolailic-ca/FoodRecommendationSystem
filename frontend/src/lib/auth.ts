/**
 * The single place where the access token is stored. Everything else — the axios
 * interceptors, the route guards, the logout hook — goes through these three
 * functions, so there is exactly one localStorage key in the app.
 */

const TOKEN_KEY = 'foodrec.access_token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    // Private browsing modes can throw on access.
    return null
  }
}

/** Message shown when the browser refuses to keep the session. */
export const STORAGE_BLOCKED_MESSAGE =
  'Your browser is blocking site data, so we cannot keep you signed in. Allow cookies and site data for this page, or leave private browsing, and try again.'

/**
 * Throws when the write fails.
 *
 * Swallowing it is worse than it looks: with no token stored, the very next
 * request comes back 401, the response interceptor clears and redirects to
 * `/login`, and the user loops through the same form forever with nothing on
 * screen to explain why. The callers turn this into the message above.
 */
export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch (cause) {
    throw new Error(STORAGE_BLOCKED_MESSAGE, { cause })
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Ignore.
  }
}

export function hasToken(): boolean {
  return getToken() !== null
}
