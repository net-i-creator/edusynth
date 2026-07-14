/**
 * УмБаза API Client
 */

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
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

    _headers(extra = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...extra,
        };
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        } else if (typeof getGuestId === 'function') {
            headers['X-Guest-Id'] = getGuestId();
        }
        return headers;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = this._headers(options.headers);

        try {
            const response = await fetch(url, { ...options, headers });

            if (response.status === 401) {
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    const retryHeaders = this._headers(options.headers);
                    const retryResponse = await fetch(url, { ...options, headers: retryHeaders });
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
            const message = typeof error.detail === 'string'
                ? error.detail
                : Array.isArray(error.detail)
                    ? error.detail.map(e => e.msg).join(', ')
                    : 'Request failed';
            throw new Error(message);
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

    async register(email, password, fullName, role = 'student', phone = null) {
        return this.request('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, password, full_name: fullName, role, phone }),
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

    async updateProfile(data) {
        return this.request('/api/auth/me', {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    async generateLesson(topic, grade, subject, educationLevel = 'school') {
        return this.request('/api/lessons/generate', {
            method: 'POST',
            body: JSON.stringify({
                topic,
                grade: parseInt(grade, 10),
                subject,
                education_level: educationLevel,
            }),
        });
    }

    async getLesson(lessonId) {
        return this.request(`/api/lessons/${lessonId}`);
    }

    async getLessonHistory() {
        return this.request('/api/lessons/history/');
    }

    async checkQuiz(lessonId, answers) {
        return this.request('/api/quiz/check', {
            method: 'POST',
            body: JSON.stringify({ lesson_id: lessonId, answers }),
        });
    }

    async getDashboardStats() {
        return this.request('/api/dashboard/stats');
    }
}

const api = new ApiClient();
