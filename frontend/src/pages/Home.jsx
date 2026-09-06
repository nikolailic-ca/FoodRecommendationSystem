import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/api";

function Home() {
    const navigate = useNavigate();

    const [recommendations, setRecommendations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    // FILTERI
    const [nameFilter, setNameFilter] = useState("");
    const [maxMinutes, setMaxMinutes] = useState("");
    const [ingredientInput, setIngredientInput] = useState("");
    const [selectedIngredients, setSelectedIngredients] = useState([]);

    const [ingredientSuggestions, setIngredientSuggestions] = useState([]);
    const [filterLoading, setFilterLoading] = useState(false);

    useEffect(() => {
        loadRecommendations();
    }, []);

    const loadRecommendations = async () => {
        try {
            setLoading(true);
            setError("");

            const token = localStorage.getItem("access_token");

            if (!token) {
                navigate("/login");
                return;
            }

            const response = await API.get(
                "/recommendations/me?n=10",
                {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            console.log("RECOMMENDATIONS:", response.data);

            setRecommendations(
                response.data.recommendations || []
            );

        } catch (err) {
            console.error(
                "Failed to load recommendations:",
                err
            );

            if (err.response?.status === 401) {
                localStorage.removeItem("access_token");
                navigate("/login");
                return;
            }

            setError(
                err.response?.data?.detail ||
                "Failed to load recommendations."
            );

        } finally {
            setLoading(false);
        }
    };


    // =====================================================
    // INGREDIENT SUGGESTIONS
    // =====================================================

    useEffect(() => {
    const query = ingredientInput.trim();

    if (query.length < 2) {
        setIngredientSuggestions([]);
        return;
    }

    const timeout = setTimeout(async () => {
        try {
            const response = await API.get(
                "/recommendations/ingredients",
                {
                    params: {
                        query: query
                    }
                }
            );

            setIngredientSuggestions(
                response.data.ingredients || []
            );

        } catch (err) {
            console.error(
                "Failed to load ingredient suggestions:",
                err
            );

            setIngredientSuggestions([]);
        }
    }, 300);

    return () => clearTimeout(timeout);
}, [ingredientInput]);


    // =====================================================
    // ADD INGREDIENT
    // =====================================================

    const addIngredient = (ingredient) => {

        const cleanIngredient = ingredient.trim();

        if (!cleanIngredient) {
            return;
        }

        if (
            selectedIngredients.some(
                item =>
                    item.toLowerCase() ===
                    cleanIngredient.toLowerCase()
            )
        ) {
            return;
        }

        setSelectedIngredients([
            ...selectedIngredients,
            cleanIngredient
        ]);

        setIngredientInput("");
        setIngredientSuggestions([]);
    };


    // =====================================================
    // REMOVE INGREDIENT
    // =====================================================

    const removeIngredient = (ingredient) => {

        setSelectedIngredients(
            selectedIngredients.filter(
                item => item !== ingredient
            )
        );
    };


    // =====================================================
    // APPLY FILTERS
    // =====================================================

    const applyFilters = async () => {
    try {
        setFilterLoading(true);
        setError("");

        const token = localStorage.getItem("access_token");

        if (!token) {
            navigate("/login");
            return;
        }

        const response = await API.get("/recommendations/me", {
            params: {
                n: 10,
                name: nameFilter.trim() || undefined,
                max_minutes: maxMinutes
                    ? Number(maxMinutes)
                    : undefined,
                ingredients:
                    selectedIngredients.length > 0
                        ? selectedIngredients.join(",")
                        : undefined,
            },
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        setRecommendations(
            response.data.recommendations || []
        );

    } catch (err) {
        console.error(
            "Failed to filter recipes:",
            err
        );

        if (err.response?.status === 401) {
            localStorage.removeItem("access_token");
            navigate("/login");
            return;
        }

        setError(
            err.response?.data?.detail ||
            "Failed to filter recipes."
        );

    } finally {
        setFilterLoading(false);
    }
};


    // =====================================================
    // CLEAR FILTERS
    // =====================================================

    const clearFilters = async () => {

        setNameFilter("");
        setMaxMinutes("");
        setIngredientInput("");
        setSelectedIngredients([]);
        setIngredientSuggestions([]);

        await loadRecommendations();
    };


    const handleLogout = () => {
        localStorage.removeItem("access_token");
        navigate("/login");
    };


    if (loading) {
        return (
            <div className="home-page">
                <div className="home-container">
                    <h2>Finding recipes for you...</h2>

                    <p>
                        We're looking for some recipes
                        you might enjoy.
                    </p>
                </div>
            </div>
        );
    }


    if (error) {
        return (
            <div className="home-page">
                <div className="home-container">

                    <div className="error-message">
                        {error}
                    </div>

                    <button
                        className="primary-button"
                        onClick={loadRecommendations}
                    >
                        Try again
                    </button>

                </div>
            </div>
        );
    }


    return (
        <div className="home-page">

            {/* =================================================
                HEADER
            ================================================= */}

            <header className="home-header">

                <div>

                    <p className="home-subtitle">
                        YOUR RECOMMENDATIONS
                    </p>

                    <h1>
                        What should you eat today?
                    </h1>

                    <p>
                        Here are some recipes recommended
                        especially for you.
                    </p>

                </div>

               <div className="header-actions">

    <button
        onClick={() => navigate("/profile")}
        className="profile-button"
    >
        Profile
    </button>

    <button
        onClick={handleLogout}
        className="logout-button"
    >
        Logout
    </button>

</div>

            </header>


            <section className="recommendations-section">

                {/* =================================================
                    FILTERS
                ================================================= */}

                <div className="recipe-filters">

                    <div className="filter-header">

                        <div>
                            <h2>Find a recipe</h2>

                            <p>
                                Filter recipes by your preferences.
                            </p>
                        </div>

                        <button
                            type="button"
                            className="clear-filters-button"
                            onClick={clearFilters}
                        >
                            Clear filters
                        </button>

                    </div>


                    <div className="filters-grid">

                        {/* NAME */}

                        <div className="filter-group filter-name">

                            <label>
                                Recipe name
                            </label>

                            <input
                                type="text"
                                value={nameFilter}
                                onChange={(e) =>
                                    setNameFilter(e.target.value)
                                }
                                placeholder="e.g. pizza, burger..."
                            />

                        </div>


                        {/* TIME */}

                        <div className="filter-group">

                            <label>
                                Maximum cooking time
                            </label>

                            <select
                                value={maxMinutes}
                                onChange={(e) =>
                                    setMaxMinutes(e.target.value)
                                }
                            >

                                <option value="">
                                    Any time
                                </option>

                                <option value="15">
                                    Up to 15 minutes
                                </option>

                                <option value="30">
                                    Up to 30 minutes
                                </option>

                                <option value="45">
                                    Up to 45 minutes
                                </option>

                                <option value="60">
                                    Up to 1 hour
                                </option>

                                <option value="120">
                                    Up to 2 hours
                                </option>

                            </select>

                        </div>


                        {/* INGREDIENTS */}

                        <div className="filter-group filter-ingredients">

                            <label>
                                Ingredients
                            </label>

                            <div className="ingredient-input-wrapper">

                                <input
                                    type="text"
                                    value={ingredientInput}
                                    onChange={(e) =>
    setIngredientInput(e.target.value)
}
                                    onKeyDown={(e) => {

                                        if (
                                            e.key === "Enter" &&
                                            ingredientInput.trim()
                                        ) {
                                            e.preventDefault();

                                            addIngredient(
                                                ingredientInput
                                            );
                                        }

                                    }}
                                    placeholder="Start typing an ingredient..."
                                />


                                {ingredientSuggestions.length > 0 && (

                                    <div className="ingredient-suggestions">

                                        {ingredientSuggestions.map(
                                            (ingredient) => (

                                                <button
                                                    key={ingredient}
                                                    type="button"
                                                    onClick={() =>
                                                        addIngredient(
                                                            ingredient
                                                        )
                                                    }
                                                >
                                                    {ingredient}
                                                </button>

                                            )
                                        )}

                                    </div>

                                )}

                            </div>


                            {/* SELECTED INGREDIENTS */}

                            {selectedIngredients.length > 0 && (

                                <div className="selected-ingredients">

                                    {selectedIngredients.map(
                                        (ingredient) => (

                                            <span
                                                key={ingredient}
                                                className="ingredient-tag"
                                            >

                                                {ingredient}

                                                <button
                                                    type="button"
                                                    onClick={() =>
                                                        removeIngredient(
                                                            ingredient
                                                        )
                                                    }
                                                >
                                                    ×
                                                </button>

                                            </span>

                                        )
                                    )}

                                </div>

                            )}

                        </div>

                    </div>


                    <button
                        type="button"
                        className="apply-filters-button"
                        onClick={applyFilters}
                        disabled={filterLoading}
                    >
                        {filterLoading
                            ? "Finding recipes..."
                            : "Apply filters"
                        }
                    </button>

                </div>


                {/* =================================================
                    TITLE
                ================================================= */}

                <div className="recommendations-title">

                    <div>
                        <h2>
                            Recommended for you
                        </h2>

                        <p className="recommendations-description">
                            Recipes selected based on your preferences.
                        </p>
                    </div>

                    <span>
                        {recommendations.length} recipes
                    </span>

                </div>


                {/* =================================================
                    RECIPES
                ================================================= */}

                {recommendations.length === 0 ? (

                    <div className="empty-state">

                        <h3>
                            No recipes found
                        </h3>

                        <p>
                            Try changing your filters and
                            search again.
                        </p>

                    </div>

                ) : (

                    <div className="recommendations-grid">

                        {recommendations.map((recipe) => (

                            <article
                                key={recipe.recipe_id}
                                className="recommendation-card"
                            >

                                <div className="recipe-image-placeholder">
                                    🍽️
                                </div>

                                <h3>
                                    {recipe.name}
                                </h3>

                                <p className="recipe-description">
                                    {recipe.description}
                                </p>

                                <div className="recipe-meta">

                                    <span>
                                        ⏱️ {recipe.minutes} min
                                    </span>

                                    <span>
                                        ⭐ {recipe.rating_count}
                                    </span>

                                </div>

                                <button
                                    className="view-recipe-button"
                                    onClick={() =>
                                        navigate(
                                            `/recipes/${recipe.recipe_id}`
                                        )
                                    }
                                >
                                    View recipe →
                                </button>

                            </article>

                        ))}

                    </div>

                )}

            </section>

        </div>
    );
}

export default Home;