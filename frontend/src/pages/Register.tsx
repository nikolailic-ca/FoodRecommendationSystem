import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { register } from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { setToken } from '@/lib/auth'
import { queryKeys } from '@/lib/queryKeys'

/**
 * Placeholder: the wiring only. Registration signs the user straight in and
 * hands them to onboarding, which is where the taste profile comes from.
 */
function Register() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const mutation = useMutation({
    mutationFn: () => register({ username, email, password }),
    onSuccess: (data) => {
      setToken(data.access_token)
      queryClient.clear()
      queryClient.setQueryData(queryKeys.me(), data.user)
      navigate('/onboarding', { replace: true })
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <AuthLayout>
      <h1 className="text-3xl font-extrabold tracking-[-0.035em]">
        Create your account
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Five ratings and the recommendations start working.
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
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        {mutation.isError ? (
          <p role="alert" className="text-sm font-medium text-destructive">
            {getErrorMessage(mutation.error, 'Registration failed.')}
          </p>
        ) : null}

        <Button type="submit" size="lg" disabled={mutation.isPending}>
          {mutation.isPending ? 'Creating account…' : 'Create account'}
        </Button>
      </form>

      <p className="mt-6 text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link to="/login" className="font-semibold text-primary">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}

export default Register
