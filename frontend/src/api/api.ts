import axios from 'axios'

export interface TokenResponse {
  access_token: string
  token_type: string
}

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8001',
})

export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const formData = new URLSearchParams()

  formData.append('username', username)
  formData.append('password', password)

  const response = await API.post<TokenResponse>('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })

  return response.data
}

export async function register(
  username: string,
  email: string,
  password: string,
): Promise<unknown> {
  const response = await API.post('/auth/register', {
    username,
    email,
    password,
  })

  return response.data
}

export default API
