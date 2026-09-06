import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Home from "./pages/Home";
import ProtectedRoute from "./ProtectedRoute";
import RateRecipes from "./pages/RateRecipes";
import RecipeDetails from "./pages/RecipeDetails";
import Profile from "./pages/Profile";
function StartPage() {
    const token = localStorage.getItem("access_token");

    if (token) {
        return <Navigate to="/home" replace />;
    }

    return <Navigate to="/login" replace />;
}


function App() {
    return (
        <BrowserRouter>
            <Routes>

                {/* početna ruta */}
                <Route
                    path="/"
                    element={<StartPage />}
                />

                {/* javne stranice */}
                <Route
                    path="/login"
                    element={<Login />}
                />

                <Route
                    path="/register"
                    element={<Register />}
                />

                {/* zaštićena glavna stranica */}
                <Route
                    path="/home"
                    element={
                        <ProtectedRoute>
                            <Home />
                        </ProtectedRoute>
                    }
                />

                {/* nepostojeća ruta */}
                <Route
                    path="*"
                    element={<Navigate to="/" replace />}
                />

                <Route
    path="/rate-recipes"
    element={<RateRecipes />}
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
            </Routes>
        </BrowserRouter>
    );
}

export default App;