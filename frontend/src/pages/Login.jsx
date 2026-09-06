import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login } from "../api/api";

function Login() {
    const navigate = useNavigate();

    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");
    setLoading(true);

    try {
    console.log("LOGIN USERNAME:", username);
    console.log("LOGIN PASSWORD:", password);

    const data = await login(username, password);

    console.log("LOGIN RESPONSE:", data);

    localStorage.setItem(
        "access_token",
        data.access_token
    );

    navigate("/home");

} catch (err) {
    console.log("LOGIN ERROR:", err);
    console.log("STATUS:", err.response?.status);
    console.log("DATA:", err.response?.data);

    setError(
        err.response?.data?.detail ||
        "Login failed."
    );

} finally {
    setLoading(false);
}
};

    return (
        <div className="auth-page">
            <div className="auth-card">
                <div className="auth-header">
                    <h1>FoodRec</h1>
                    <p>Discover recipes you'll love.</p>
                </div>

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Username</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="Enter your username"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Enter your password"
                            required
                        />
                    </div>

                    {error && (
                        <div className="error-message">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="primary-button"
                        disabled={loading}
                    >
                        {loading ? "Signing in..." : "Sign in"}
                    </button>
                </form>

                <div className="auth-footer">
                    <span>Don't have an account?</span>
                    <Link to="/register">Create account</Link>
                </div>
            </div>
        </div>
    );
}

export default Login;