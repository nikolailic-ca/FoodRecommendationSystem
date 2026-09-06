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

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Nothing sensible to do: the session simply will not survive a reload.
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
