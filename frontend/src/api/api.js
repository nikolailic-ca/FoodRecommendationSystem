import axios from "axios";

const API = axios.create({
    baseURL: "http://127.0.0.1:8001",
});

export const login = async (username, password) => {
    const formData = new URLSearchParams();

    formData.append("username", username);
    formData.append("password", password);

    const response = await API.post(
        "/auth/login",
        formData,
        {
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
        }
    );

    return response.data;
};

export const register = async (username, email, password) => {
    const response = await API.post(
        "/auth/register",
        {
            username,
            email,
            password,
        }
    );

    return response.data;
};

export default API;