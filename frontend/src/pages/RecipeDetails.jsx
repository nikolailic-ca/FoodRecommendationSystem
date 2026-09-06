import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import API from "../api/api";

function RecipeDetails() {

    const { recipeId } = useParams();
    const navigate = useNavigate();

   const [recipe, setRecipe] = useState(null);
const [rating, setRating] = useState(0);
const [existingRating, setExistingRating] = useState(null);
const [loading, setLoading] = useState(true);
const [submitting, setSubmitting] = useState(false);
const [error, setError] = useState("");
const [success, setSuccess] = useState("");

    useEffect(() => {
        loadRecipe();
    }, [recipeId]);

    const loadRecipe = async () => {
    try {
        const token = localStorage.getItem("access_token");

        const headers = {
            Authorization: `Bearer ${token}`,
        };

        const [recipeResponse, ratingsResponse] =
            await Promise.all([
                API.get(`/recipes/${recipeId}`),
                API.get("/users/me/ratings", { headers }),
            ]);

        setRecipe(recipeResponse.data);

        const userRating = ratingsResponse.data.ratings?.find(
            item => item.recipe_id === Number(recipeId)
        );

        if (userRating) {
            setExistingRating(userRating.rating);
            setRating(userRating.rating);
        } else {
            setExistingRating(null);
            setRating(0);
        }

    } catch (err) {

        console.error(
            "Failed to load recipe:",
            err
        );

        setError(
            err.response?.data?.detail ||
            "Failed to load recipe."
        );

    } finally {
        setLoading(false);
    }
};


    const handleRating = (value) => {
        setRating(value);
        setSuccess("");
    };


    const handleSubmitRating = async () => {

        if (rating === 0) {
            return;
        }

        setSubmitting(true);
        setError("");
        setSuccess("");

        try {

           const token = localStorage.getItem("access_token");

await API.post(
    "/users/me/ratings",
    {
        recipe_id: Number(recipeId),
        rating: rating
    },
    {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    }
);

            setSuccess(
                "Your rating has been saved!"
            );

        } catch (err) {

            console.error(
                "Failed to save rating:",
                err
            );

            setError(
                err.response?.data?.detail ||
                "Failed to save rating."
            );

        } finally {

            setSubmitting(false);

        }
    };


    if (loading) {
        return (
            <div className="recipe-details-page">
                <div className="recipe-details-card">
                    <h2>Loading recipe...</h2>
                </div>
            </div>
        );
    }


    if (error && !recipe) {
        return (
            <div className="recipe-details-page">
                <div className="recipe-details-card">

                    <div className="error-message">
                        {error}
                    </div>

                    <button
                        className="secondary-button"
                        onClick={() => navigate("/")}
                    >
                        Back to recommendations
                    </button>

                </div>
            </div>
        );
    }


    if (!recipe) {
        return null;
    }


    let ingredients = [];
    let steps = [];

    try {
        ingredients =
            typeof recipe.ingredients === "string"
                ? JSON.parse(
                    recipe.ingredients.replaceAll("'", '"')
                )
                : recipe.ingredients || [];
    } catch {
        ingredients = [recipe.ingredients];
    }


    try {
        steps =
            typeof recipe.steps === "string"
                ? JSON.parse(
                    recipe.steps.replaceAll("'", '"')
                )
                : recipe.steps || [];
    } catch {
        steps = [recipe.steps];
    }


    return (
        <div className="recipe-details-page">

            <div className="recipe-details-card">

                <button
                    className="back-button"
                    onClick={() => navigate("/")}
                >
                    ← Back to recommendations
                </button>


                <div className="recipe-details-header">

                    <div className="recipe-icon">
                        🍽️
                    </div>

                    <h1>
                        {recipe.name}
                    </h1>

                    <p>
                        {recipe.description}
                    </p>

                    <div className="recipe-details-meta">

                        <span>
                            ⏱ {recipe.minutes} min
                        </span>

                        <span>
                            👨‍🍳 {recipe.n_steps} steps
                        </span>

                    </div>

                </div>


                <div className="recipe-details-content">


                    <section>

                        <h2>Ingredients</h2>

                        <ul className="ingredients-list">

                            {ingredients.map(
                                (ingredient, index) => (
                                    <li key={index}>
                                        {ingredient}
                                    </li>
                                )
                            )}

                        </ul>

                    </section>


                    <section>

                        <h2>Instructions</h2>

                        <ol className="steps-list">

                            {steps.map(
                                (step, index) => (
                                    <li key={index}>
                                        {step}
                                    </li>
                                )
                            )}

                        </ol>

                    </section>


                    <section className="rating-box">

    {existingRating !== null ? (
        <>
            <h2>
                Your rating
            </h2>

            <p>
                You have already rated this recipe.
            </p>

            <div className="detail-stars">
                {[1, 2, 3, 4, 5].map(
                    (value) => (
                        <span
                            key={value}
                            className={
                                value <= existingRating
                                    ? "detail-star selected"
                                    : "detail-star"
                            }
                        >
                            ★
                        </span>
                    )
                )}
            </div>

            <div className="rating-value">
                You rated this recipe {existingRating} / 5
            </div>
        </>
    ) : (
        <>
            <h2>
                What do you think?
            </h2>

            <p>
                Rate this recipe from 1 to 5 stars.
            </p>

            <div className="detail-stars">

                {[1, 2, 3, 4, 5].map(
                    (value) => (
                        <button
                            key={value}
                            type="button"
                            className={
                                value <= rating
                                    ? "detail-star selected"
                                    : "detail-star"
                            }
                            onClick={() =>
                                handleRating(value)
                            }
                        >
                            ★
                        </button>
                    )
                )}

            </div>

            <div className="rating-value">

                {rating === 0
                    ? "Select a rating"
                    : `${rating} / 5`
                }

            </div>

            {error && (
                <div className="error-message">
                    {error}
                </div>
            )}

            {success && (
                <div className="success-message">
                    {success}
                </div>
            )}

            <button
                className="primary-button"
                onClick={handleSubmitRating}
                disabled={
                    rating === 0 ||
                    submitting
                }
            >
                {submitting
                    ? "Saving..."
                    : "Rate recipe"
                }
            </button>
        </>
    )}

</section>

                </div>

            </div>

        </div>
    );
}

export default RecipeDetails;