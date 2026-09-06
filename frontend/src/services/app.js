const API_URL = "http://127.0.0.1:8001";

export async function login(username, password) {
    const formData = new URLSearchParams();

    formData.append("username", username);
    formData.append("password", password);

    const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Login failed");
    }

    localStorage.setItem("access_token", data.access_token);

    return data;
}


export async function register(username, email, password) {
    const response = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            username,
            email,
            password,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Registration failed");
    }

    return data;
}


export async function getCurrentUser() {
    const token = localStorage.getItem("access_token");

    const response = await fetch(`${API_URL}/users/me`, {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Failed to get user");
    }

    return data;
}


export async function getRecommendations(n = 10) {
    const token = localStorage.getItem("access_token");

    const response = await fetch(
        `${API_URL}/recommendations/me?n=${n}`,
        {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.detail || "Failed to get recommendations"
        );
    }

    return data;
}


export function logout() {
    localStorage.removeItem("access_token");
}


export function isLoggedIn() {
    return Boolean(
        localStorage.getItem("access_token")
    );
}