import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './ProtectedRoute'
import Home from './pages/Home'
import Login from './pages/Login'
import Profile from './pages/Profile'
import RateRecipes from './pages/RateRecipes'
import RecipeDetails from './pages/RecipeDetails'
import Register from './pages/Register'

function StartPage() {
  const token = localStorage.getItem('access_token')

  return <Navigate to={token ? '/home' : '/login'} replace />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StartPage />} />

        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/rate-recipes" element={<RateRecipes />} />

        <Route
          path="/home"
          element={
            <ProtectedRoute>
              <Home />
            </ProtectedRoute>
          }
        />
        <Route
          path="/recipes/:recipeId"
          element={
            <ProtectedRoute>
              <RecipeDetails />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
