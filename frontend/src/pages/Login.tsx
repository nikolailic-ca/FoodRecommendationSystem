import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { login } from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { setToken } from '@/lib/auth'

/**
 * Placeholder: the wiring only. A later step builds the designed screen on top
 * of the same mutation.
 */
function Login() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: () => login({ username, password }),
    onSuccess: (data) => {
      setToken(data.access_token)
      queryClient.clear()
      navigate('/home', { replace: true })
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <AuthLayout>
      <h1 className="text-3xl font-extrabold tracking-[-0.035em]">
        Welcome back
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Sign in to pick up your recommendations.
      </p>

      <form onSubmit={handleSubmit} className="mt-7 flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="username">Username</Label>
          <Input
            id="username"
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        {mutation.isError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {getErrorMessage(mutation.error, 'Login failed.')}
          </p>
        ) : null}

        <Button type="submit" size="lg" disabled={mutation.isPending}>
          {mutation.isPending ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted-foreground">
        New here?{' '}
        <Link to="/register" className="font-semibold text-primary">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  )
}

export default Login
