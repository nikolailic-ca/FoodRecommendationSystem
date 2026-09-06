import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../api/api";

function Register() {
    const navigate = useNavigate();

    const [username, setUsername] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");

    if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
    }

    setLoading(true);

    try {

        navigate("/rate-recipes", {
            state: {
                username,
                email,
                password
            }
        });

    } catch (err) {

        console.log("REGISTER ERROR:", err);

        setError(
            err.response?.data?.detail ||
            "Registration failed."
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
                    <p>Create your account.</p>
                </div>

                <form onSubmit={handleSubmit}>

                    <div className="form-group">
                        <label>Username</label>

                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="Choose a username"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Email</label>

                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="Enter your email"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Password</label>

                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Create a password"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Confirm password</label>

                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) =>
                                setConfirmPassword(e.target.value)
                            }
                            placeholder="Repeat your password"
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
                        {loading ? "Creating account..." : "Create account"}
                    </button>

                </form>

                <div className="auth-footer">
                    <span>Already have an account?</span>

                    <Link to="/login">
                        Sign in
                    </Link>
                </div>

            </div>
        </div>
    );
}

export default Register;