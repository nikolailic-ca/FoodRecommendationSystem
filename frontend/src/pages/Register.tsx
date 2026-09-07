import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Lock, Mail, User } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { register } from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import { AuthField } from '@/components/auth/AuthField'
import { AuthLayout } from '@/components/layout/AuthLayout'
import { setToken, STORAGE_BLOCKED_MESSAGE } from '@/lib/auth'
import { queryKeys } from '@/lib/queryKeys'

const MIN_PASSWORD_LENGTH = 8

/**
 * Create an account.
 *
 * Registration hands back a token with the user, so the new account is signed
 * in immediately and sent to onboarding — there is nothing to recommend from
 * until it has rated something. A taken username or email arrives as a 409 and
 * is shown verbatim.
 */
function Register() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => register({ username, email, password }),
    onSuccess: (data) => {
      try {
        setToken(data.access_token)
      } catch {
        // The account exists at this point, so "try again" would only collide
        // with the username it just took. Say what actually happened instead.
        setLocalError(
          `${STORAGE_BLOCKED_MESSAGE} Your account was created — sign in once you have.`,
        )

        return
      }

      queryClient.clear()
      // The response already carries the user, so the onboarding guard does not
      // have to wait for a `GET /users/me` before it can decide.
      queryClient.setQueryData(queryKeys.me(), data.user)
      navigate('/onboarding', { replace: true })
    },
  })

  const passwordsMatch = confirmation.length > 0 && confirmation === password

  /**
   * Editing anything clears the last complaint: leaving "the passwords do not
   * match" on screen while the user is fixing exactly that reads as broken.
   */
  function edit(setter: (value: string) => void) {
    return (value: string) => {
      setLocalError(null)
      mutation.reset()
      setter(value)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (password.length < MIN_PASSWORD_LENGTH) {
      setLocalError(`Your password needs at least ${MIN_PASSWORD_LENGTH} characters.`)

      return
    }

    if (password !== confirmation) {
      setLocalError('The two passwords do not match.')

      return
    }

    setLocalError(null)
    mutation.mutate()
  }

  const error = localError ?? (mutation.isError
    ? getErrorMessage(mutation.error, 'Could not create your account.')
    : null)

  return (
    <AuthLayout>
      <h1 className="text-3xl leading-[1.15] font-extrabold tracking-[-0.035em]">
        Create your account
      </h1>
      <p className="mt-2 text-[15px] leading-[1.55] text-muted-foreground">
        Next you will rate five recipes so we have something to work with.
      </p>

      <form onSubmit={handleSubmit} className="mt-7 flex flex-col gap-[17px]">
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
            edit(setUsername)(event.target.value)
          }}
        />

        <AuthField
          id="email"
          name="email"
          label="Email"
          type="email"
          icon={<Mail className="size-[17px]" strokeWidth={1.9} />}
          autoComplete="email"
          required
          value={email}
          onChange={(event) => {
            edit(setEmail)(event.target.value)
          }}
        />

        <AuthField
          id="password"
          name="password"
          label="Password"
          password
          icon={<Lock className="size-[17px]" strokeWidth={1.9} />}
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          value={password}
          onChange={(event) => {
            edit(setPassword)(event.target.value)
          }}
        />

        <AuthField
          id="confirmation"
          name="confirmation"
          label="Confirm password"
          password
          valid={passwordsMatch}
          icon={<Lock className="size-[17px]" strokeWidth={1.9} />}
          autoComplete="new-password"
          required
          value={confirmation}
          onChange={(event) => {
            edit(setConfirmation)(event.target.value)
          }}
        />

        {error ? (
          <p
            role="alert"
            className="rounded-xl bg-destructive/8 px-3.5 py-2.5 text-[13.5px] font-semibold text-destructive"
          >
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={mutation.isPending}
          className="mt-2 flex h-[50px] cursor-pointer items-center justify-center gap-2.5 rounded-[14px] bg-primary text-[15.5px] font-bold text-primary-foreground shadow-[0_4px_14px_rgba(63,163,77,0.32)] transition-colors outline-none hover:bg-primary/90 focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {mutation.isPending ? 'Creating account…' : 'Create account'}
          <ArrowRight className="size-[18px]" strokeWidth={1.9} />
        </button>
      </form>

      <p className="mt-[22px] text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link
          to="/login"
          className="font-bold text-primary outline-none hover:text-accent-foreground focus-visible:underline"
        >
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}

export default Register
