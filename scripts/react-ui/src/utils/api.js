import axios from 'axios';



// In Development (Vite): Use relative '/api' so Vite proxy handles it.
// In Production (Tauri): Use absolute localhost because there is no Vite proxy.
const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '1453';
const baseURL = import.meta.env.DEV ? '' : `http://127.0.0.1:${BACKEND_PORT}`;

console.log(`[API Config] Environment: ${import.meta.env.MODE}, BaseURL: ${baseURL}`);

const api = axios.create({
    baseURL: baseURL
});

// Add a response interceptor to handle errors globally
api.interceptors.response.use(
    response => response,
    error => {
        // [FIX] Allow suppressing console errors for health pings or expected failures
        if (!error.config?.silent) {
            console.error("[API Error]", error);
        }
        return Promise.reject(error);
    }
);

export default api;
