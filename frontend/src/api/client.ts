import axios, { AxiosError, AxiosHeaders } from 'axios'

import { clearToken, getToken } from '@/lib/auth'

import type { ApiErrorBody } from './types'

export const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001'

/** Requests whose 401 means "wrong password", not "session expired". */
const LOGIN_PATH = '/auth/login'

export const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { Accept: 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = getToken()

  if (token) {
    const headers = AxiosHeaders.from(config.headers)
    headers.set('Authorization', `Bearer ${token}`)
    config.headers = headers
  }

  return config
})

function isLoginRequest(error: AxiosError): boolean {
  return (error.config?.url ?? '').includes(LOGIN_PATH)
}

client.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      !isLoginRequest(error)
    ) {
      // The token is gone or expired: drop it and start over. A hard navigation
      // is deliberate — it throws away every cache the session held.
      clearToken()

      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }

    return Promise.reject(error)
  },
)

const GENERIC_ERROR = 'Something went wrong. Please try again.'
const OFFLINE_ERROR =
  'Cannot reach the server. Check that the backend is running on port 8001.'

/**
 * Turns anything thrown by the client into a sentence that can be shown to a
 * user. FastAPI answers with `{"detail": "..."}` for handled errors and with
 * `{"detail": [{loc, msg, type}, ...]}` for request validation failures.
 */
export function getErrorMessage(
  error: unknown,
  fallback: string = GENERIC_ERROR,
): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    if (!error.response) {
      return OFFLINE_ERROR
    }

    const detail = error.response.data?.detail

    if (typeof detail === 'string' && detail.trim() !== '') {
      return detail
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => item.msg)
        .filter((message): message is string => Boolean(message))

      if (messages.length > 0) {
        return messages.join('. ')
      }
    }

    return fallback
  }

  if (error instanceof Error && error.message !== '') {
    return error.message
  }

  return fallback
}

export default client
