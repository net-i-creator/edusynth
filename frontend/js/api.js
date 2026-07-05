/**
 * УмБаза API Client
 */

const API_BASE = window.location.hostname === 'localhost'
    ? 'http://localhost:8001'
    : window.location.origin;

class ApiClient {
    constructor() {
        this.baseUrl = API_BASE;
    }

    getToken() {
        return localStorage.getItem('access_token');
    }

    setTokens(access, refresh) {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
    }

    clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, { ...options, headers });

            if (response.status === 401) {
                // Try refresh
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    headers['Authorization'] = `Bearer ${this.getToken()}`;
                    const retryResponse = await fetch(url, { ...options, headers });
                    return this.handleResponse(retryResponse);
                }
                this.clearTokens();
                return null;
            }

            return this.handleResponse(response);
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    async handleResponse(response) {
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Network error' }));
            throw new Error(error.detail || 'Request failed');
        }
        return response.json();
    }

    async refreshToken() {
        const refresh = localStorage.getItem('refresh_token');
        if (!refresh) return false;

        try {
            const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refresh }),
            });

            if (response.ok) {
                const data = await response.json();
                this.setTokens(data.access_token, data.refresh_token);
                return true;
            }
        } catch (e) {
            console.error('Token refresh failed:', e);
        }

        return false;
    }

    // Auth endpoints
    async register(email, password, fullName) {
        return this.request('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, password, full_name: fullName }),
        });
    }

    async login(email, password) {
        return this.request('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
    }

    async getMe() {
        return this.request('/api/auth/me');
    }

    // Lesson endpoints
    async generateLesson(topic, grade, subject) {
        return this.request('/api/lessons/generate', {
            method: 'POST',
            body: JSON.stringify({ topic, grade: parseInt(grade), subject }),
        });
    }

    async getLesson(lessonId) {
        return this.request(`/api/lessons/${lessonId}`);
    }

    async getLessonHistory() {
        return this.request('/api/lessons/history/');
    }

    // Quiz endpoints
    async checkQuiz(lessonId, answers) {
        return this.request('/api/quiz/check', {
            method: 'POST',
            body: JSON.stringify({ lesson_id: lessonId, answers }),
        });
    }

    // Dashboard
    async getDashboardStats() {
        return this.request('/api/dashboard/stats');
    }
}

// Global instance
const api = new ApiClient();
