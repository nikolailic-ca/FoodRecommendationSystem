import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import {
  RequireOnboarded,
  RequireOnboarding,
} from '@/components/auth/OnboardingGuard'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { PublicOnlyRoute } from '@/components/auth/PublicOnlyRoute'
import { AppShell } from '@/components/layout/AppShell'
import { hasToken } from '@/lib/auth'
import Home from '@/pages/Home'
import Login from '@/pages/Login'
import Onboarding from '@/pages/Onboarding'
import Profile from '@/pages/Profile'
import RecipeDetails from '@/pages/RecipeDetails'
import Register from '@/pages/Register'

/** Entry point: signed in goes to the recommendations, signed out to login. */
function StartPage() {
  return <Navigate to={hasToken() ? '/home' : '/login'} replace />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StartPage />} />

        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<RequireOnboarding />}>
            <Route path="/onboarding" element={<Onboarding />} />
          </Route>

          <Route element={<RequireOnboarded />}>
            <Route element={<AppShell />}>
              <Route path="/home" element={<Home />} />
              <Route path="/recipes/:recipeId" element={<RecipeDetails />} />
              <Route path="/profile" element={<Profile />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
