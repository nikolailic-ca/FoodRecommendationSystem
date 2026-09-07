import { client } from './client'
import type {
  AuthToken,
  LoginPayload,
  RegisterPayload,
  RegisterResponse,
} from './types'

/**
 * `POST /auth/login`
 *
 * FastAPI's OAuth2 password flow expects `application/x-www-form-urlencoded`,
 * not JSON. A 401 here means the credentials were wrong; the response
 * interceptor deliberately lets it through so the form can show the message.
 */
export async function login(payload: LoginPayload): Promise<AuthToken> {
  const body = new URLSearchParams()
  body.set('username', payload.username)
  body.set('password', payload.password)

  const { data } = await client.post<AuthToken>('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })

  return data
}

/** `POST /auth/register` — 201 with a token, 409 if the name or email is taken. */
export async function register(
  payload: RegisterPayload,
): Promise<RegisterResponse> {
  const { data } = await client.post<RegisterResponse>('/auth/register', payload)

  return data
}
