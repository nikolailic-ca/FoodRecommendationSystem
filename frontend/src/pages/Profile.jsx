import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/api";

function Profile() {
    const navigate = useNavigate();

    const [user, setUser] = useState(null);
    const [ratings, setRatings] = useState([]);
    const [ratingFilter, setRatingFilter] = useState("all");

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        loadProfile();
    }, []);

    const loadProfile = async () => {
        try {
            setLoading(true);
            setError("");

            const token = localStorage.getItem("access_token");

            if (!token) {
                navigate("/login");
                return;
            }

            const headers = {
                Authorization: `Bearer ${token}`,
            };

            const [userResponse, ratingsResponse] =
                await Promise.all([
                    API.get("/users/me", { headers }),
                    API.get("/users/me/ratings", { headers }),
                ]);

            setUser(userResponse.data);
            setRatings(
                ratingsResponse.data.ratings || []
            );

        } catch (err) {
            console.error(
                "Failed to load profile:",
                err
            );

            if (err.response?.status === 401) {
                localStorage.removeItem("access_token");
                navigate("/login");
                return;
            }

            setError(
                err.response?.data?.detail ||
                "Failed to load profile."
            );

        } finally {
            setLoading(false);
        }
    };


    // =====================================================
    // FILTER RATINGS
    // =====================================================

    const filteredRatings =
        ratingFilter === "all"
            ? ratings
            : ratings.filter(
                  item =>
                      item.rating ===
                      Number(ratingFilter)
              );


    // =====================================================
    // STARS
    // =====================================================

    const renderStars = (rating) => {
        return (
            "★".repeat(rating) +
            "☆".repeat(5 - rating)
        );
    };


    // =====================================================
    // LOADING
    // =====================================================

    if (loading) {
        return (
            <div className="profile-page">
                <div className="profile-container">

                    <div className="profile-card">
                        <h2>
                            Loading your profile...
                        </h2>
                    </div>

                </div>
            </div>
        );
    }


    // =====================================================
    // ERROR
    // =====================================================

    if (error) {
        return (
            <div className="profile-page">
                <div className="profile-container">

                    <div className="profile-card">

                        <div className="error-message">
                            {error}
                        </div>

                        <button
                            className="primary-button"
                            onClick={loadProfile}
                        >
                            Try again
                        </button>

                    </div>

                </div>
            </div>
        );
    }


    return (
        <div className="profile-page">

            <div className="profile-container">

                {/* =================================================
                    HEADER
                ================================================= */}

                <header className="home-header">

                    <div>

                        <p className="home-subtitle">
                            MY ACCOUNT
                        </p>

                        <h1>
                            My Profile
                        </h1>

                        <p>
                            Your account information
                            and rated recipes.
                        </p>

                    </div>

                    <button
                        className="profile-button"
                        onClick={() =>
                            navigate("/home")
                        }
                    >
                        Back to home
                    </button>

                </header>


                {/* =================================================
                    ACCOUNT INFORMATION
                ================================================= */}

                <div className="profile-card">

                    <div className="profile-card-header">

                        <div className="profile-avatar">
                            {user?.username
                                ?.charAt(0)
                                .toUpperCase()}
                        </div>

                        <div>

                            <p className="profile-label">
                                ACCOUNT
                            </p>

                            <h2>
                                {user?.username}
                            </h2>

                        </div>

                    </div>


                    <div className="profile-details">

                        <div className="profile-detail">

                            <span>
                                Username
                            </span>

                            <strong>
                                {user?.username}
                            </strong>

                        </div>


                        <div className="profile-detail">

                            <span>
                                Email
                            </span>

                            <strong>
                                {user?.email}
                            </strong>

                        </div>

                    </div>

                </div>


                {/* =================================================
                    RATINGS HEADER
                ================================================= */}

                <div className="profile-ratings-header">

                    <div>

                        <p className="home-subtitle">
                            RATING HISTORY
                        </p>

                        <h2>
                            My rated recipes
                        </h2>

                        <p>
                            Recipes you have rated
                            and your personal ratings.
                        </p>

                    </div>


                    <div className="rating-filter">

                        <label>
                            Show
                        </label>

                        <select
                            value={ratingFilter}
                            onChange={(e) =>
                                setRatingFilter(
                                    e.target.value
                                )
                            }
                        >

                            <option value="all">
                                All ratings
                            </option>

                            <option value="5">
                                ★★★★★ 5 stars
                            </option>

                            <option value="4">
                                ★★★★☆ 4 stars
                            </option>

                            <option value="3">
                                ★★★☆☆ 3 stars
                            </option>

                            <option value="2">
                                ★★☆☆☆ 2 stars
                            </option>

                            <option value="1">
                                ★☆☆☆☆ 1 star
                            </option>

                        </select>

                    </div>

                </div>


                {/* =================================================
                    RATED RECIPES
                ================================================= */}

                {filteredRatings.length === 0 ? (

                    <div className="empty-state">

                        <h3>
                            No rated recipes
                        </h3>

                        <p>
                            You haven't rated any recipes
                            with this rating yet.
                        </p>

                    </div>

                ) : (

                    <div className="recommendations-grid">

                        {filteredRatings.map(
                            (recipe) => (

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


                                    <div className="profile-rating">

                                        <span>
                                            {renderStars(
                                                recipe.rating
                                            )}
                                        </span>

                                        <strong>
                                            {recipe.rating}/5
                                        </strong>

                                    </div>


                                    <p className="recipe-description">
                                        {recipe.description}
                                    </p>


                                    <div className="recipe-meta">

                                        <span>
                                            ⏱️{" "}
                                            {recipe.minutes} min
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

                            )
                        )}

                    </div>

                )}

            </div>

        </div>
    );
}

export default Profile;