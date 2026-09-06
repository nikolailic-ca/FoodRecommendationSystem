import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import API from "../api/api";

function RateRecipes() {
    const navigate = useNavigate();
    const location = useLocation();

    const registrationData = location.state;

    const [recipes, setRecipes] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [ratings, setRatings] = useState({});
    const [selectedRating, setSelectedRating] = useState(0);

    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (!registrationData) {
            navigate("/register");
            return;
        }

        loadRecipes();
    }, []);

    const loadRecipes = async () => {
        try {
            const response = await API.get(
                "/recommendations/onboarding?n=10"
            );

            setRecipes(response.data.recipes);
        } catch (err) {
            console.error("Failed to load recipes:", err);

            setError(
                "Failed to load recipes. Please try again."
            );
        } finally {
            setLoading(false);
        }
    };

    const handleRating = (rating) => {
        setSelectedRating(rating);
    };

    // ============================================================
    // NEXT / SAVE RATING
    // ============================================================

    const handleNext = async () => {
    if (selectedRating === 0) {
        return;
    }

    const currentRecipe = recipes[currentIndex];

    const updatedRatings = {
        ...ratings,
        [currentRecipe.id]: selectedRating
    };

    setRatings(updatedRatings);

    if (currentIndex < recipes.length - 1) {
        setCurrentIndex(currentIndex + 1);
        setSelectedRating(0);
        setError("");
        return;
    }

    // Poslednji recept — minimum 5 ocena.
    if (Object.keys(updatedRatings).length < 5) {
        setError(
            `Please rate at least 5 recipes before finishing. You have rated ${Object.keys(updatedRatings).length}.`
        );
        return;
    }

    await finishRegistration(updatedRatings);
};

    // ============================================================
    // SKIP
    // ============================================================

    const handleSkip = async () => {
    const currentRecipe = recipes[currentIndex];

    console.log(
        "Skipped recipe:",
        currentRecipe.id,
        currentRecipe.name
    );

    if (currentIndex < recipes.length - 1) {
        setCurrentIndex(currentIndex + 1);
        setSelectedRating(0);
        return;
    }

    // Poslednji recept — proveravamo minimum ocena.
    if (Object.keys(ratings).length < 5) {
        setError(
            `Please rate at least 5 recipes before finishing. You have rated ${Object.keys(ratings).length}.`
        );
        return;
    }

    await finishRegistration(ratings);
};

    // ============================================================
    // FINISH REGISTRATION
    // ============================================================

    const finishRegistration = async (finalRatings) => {
        setSubmitting(true);
        setError("");

        try {
            const ratingsArray = Object.entries(finalRatings).map(
                ([recipe_id, rating]) => ({
                    recipe_id: Number(recipe_id),
                    rating: Number(rating)
                })
            );

            console.log("Final ratings:", ratingsArray);

            await API.post("/auth/register", {
                username: registrationData.username,
                email: registrationData.email,
                password: registrationData.password,
                ratings: ratingsArray
            });

            navigate("/login", {
                state: {
                    message:
                        "Account created successfully. You can now sign in."
                }
            });

        } catch (err) {
            console.error("Registration error:", err);

            setError(
                err.response?.data?.detail ||
                "Registration failed."
            );

            setSubmitting(false);
        }
    };

    // ============================================================
    // LOADING
    // ============================================================

    if (loading) {
        return (
            <div className="auth-page">
                <div className="auth-card">
                    <h2>Loading recipes...</h2>
                </div>
            </div>
        );
    }

    // ============================================================
    // ERROR
    // ============================================================

    if (error) {
        return (
            <div className="auth-page">
                <div className="auth-card">

                    <div className="error-message">
                        {error}
                    </div>

                    <button
                        className="primary-button"
                        onClick={() => window.location.reload()}
                    >
                        Try again
                    </button>

                </div>
            </div>
        );
    }

    // ============================================================
    // NO RECIPES
    // ============================================================

    if (recipes.length === 0) {
        return (
            <div className="auth-page">
                <div className="auth-card">
                    <h2>No recipes available.</h2>
                </div>
            </div>
        );
    }

    const currentRecipe = recipes[currentIndex];

    // ============================================================
    // UI
    // ============================================================

    return (
        <div className="rating-page">

            <div className="rating-card">

               <div className="rating-header">

    <span className="rating-step">
        Recipe {currentIndex + 1} of {recipes.length}
    </span>

    <h1>Tell us what you like</h1>

    <p>
        Rate these recipes so we can recommend
        better food for you.
    </p>

</div>

<p className="rating-progress">
    Rated {Object.keys(ratings).length} / 5 required recipes
</p>

<div className="recipe-card">

                    <div className="recipe-placeholder">
                        🍽️
                    </div>

                    <div className="recipe-info">

                        <h2>
                            {currentRecipe.name}
                        </h2>

                        {currentRecipe.description && (
                            <p>
                                {currentRecipe.description}
                            </p>
                        )}

                        <div className="recipe-meta">

                            <span>
                                ⏱ {currentRecipe.minutes} min
                            </span>

                            <span>
                                ⭐ {currentRecipe.rating_count} ratings
                            </span>

                        </div>

                    </div>

                </div>

                <div className="rating-section">

                    <h3>
                        How much would you like this?
                    </h3>

                    <div className="stars">

                        {[1, 2, 3, 4, 5].map((rating) => (
                            <button
                                key={rating}
                                type="button"
                                className={
                                    rating <= selectedRating
                                        ? "star selected"
                                        : "star"
                                }
                                onClick={() =>
                                    handleRating(rating)
                                }
                            >
                                ★
                            </button>
                        ))}

                    </div>

                    <div className="rating-label">
                        {selectedRating === 0
                            ? "Select a rating"
                            : `${selectedRating} / 5`
                        }
                    </div>

                </div>

                {/* ==================================================
                    ACTIONS
                ================================================== */}

                <button
                    className="primary-button"
                    onClick={handleNext}
                    disabled={
                        selectedRating === 0 ||
                        submitting
                    }
                >
                    {submitting
                        ? "Creating account..."
                        : currentIndex === recipes.length - 1
                            ? "Finish"
                            : "Next"
                    }
                </button>

                <button
                    type="button"
                    className="skip-button"
                    onClick={handleSkip}
                    disabled={submitting}
                >
                    Skip
                </button>

            </div>

        </div>
    );
}

export default RateRecipes;