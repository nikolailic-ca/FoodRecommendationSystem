import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Lock, User } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { login } from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import { AuthField } from '@/components/auth/AuthField'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { setToken } from '@/lib/auth'

/**
 * Sign in.
 *
 * A wrong password comes back as a 401, which the response interceptor lets
 * through on purpose so the message below the form can be the backend's own.
 * Nothing here logs, stores or navigates with the credentials.
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
      // Anything cached under the previous session belongs to another user.
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
      <h1 className="text-3xl leading-[1.15] font-extrabold tracking-[-0.035em]">
        Welcome back
      </h1>
      <p className="mt-2 text-[15px] leading-[1.55] text-muted-foreground">
        Sign in to pick up your recommendations.
      </p>

      <form onSubmit={handleSubmit} className="mt-[30px] flex flex-col gap-[18px]">
        <AuthField
          id="username"
          name="username"
          label="Username"
          icon={<User className="size-[17px]" strokeWidth={1.9} />}
          autoComplete="username"
          autoFocus
          required
          value={username}
          onChange={(event) => {
            setUsername(event.target.value)
          }}
        />

        <AuthField
          id="password"
          name="password"
          label="Password"
          password
          icon={<Lock className="size-[17px]" strokeWidth={1.9} />}
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => {
            setPassword(event.target.value)
          }}
        />

        {mutation.isError ? (
          <p
            role="alert"
            className="rounded-xl bg-destructive/8 px-3.5 py-2.5 text-[13.5px] font-semibold text-destructive"
          >
            {getErrorMessage(mutation.error, 'Could not sign you in.')}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={mutation.isPending}
          className="mt-2 flex h-[50px] cursor-pointer items-center justify-center rounded-[14px] bg-primary text-[15.5px] font-bold text-primary-foreground shadow-[0_4px_14px_rgba(63,163,77,0.32)] transition-colors outline-none hover:bg-primary/90 focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {mutation.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <div className="mt-[22px] flex items-center gap-3.5">
        <span className="h-px grow bg-border" />
        <span className="text-[12.5px] font-semibold text-ink-faint">
          NEW HERE
        </span>
        <span className="h-px grow bg-border" />
      </div>

      <Link
        to="/register"
        className="mt-5 flex h-[50px] items-center justify-center rounded-[14px] border border-border text-[15px] font-bold text-foreground transition-colors outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        Create an account
      </Link>

      <p className="mt-[26px] text-center text-[12.5px] leading-[1.6] text-ink-faint">
        Recipe data from the Food.com dataset on Kaggle.
      </p>
    </AuthLayout>
  )
}

export default Login
