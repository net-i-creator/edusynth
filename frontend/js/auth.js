/**
 * Auth utilities
 */

function isLoggedIn() {
    return !!localStorage.getItem('access_token');
}

function getUser() {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
}

function setUser(user) {
    localStorage.setItem('user', JSON.stringify(user));
}

function logout() {
    api.clearTokens();
    window.location.href = '/';
}

function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = 'auth.html';
        return false;
    }
    return true;
}

function updateAuthUI() {
    const authButtons = document.getElementById('auth-buttons');
    const userMenu = document.getElementById('user-menu');

    if (!authButtons || !userMenu) return;

    if (isLoggedIn()) {
        authButtons.classList.add('hidden');
        userMenu.classList.remove('hidden');
        const user = getUser();
        if (user) {
            const nameEl = document.getElementById('user-name');
            if (nameEl) nameEl.textContent = user.full_name || user.email;
        }
    } else {
        authButtons.classList.remove('hidden');
        userMenu.classList.add('hidden');
    }
}

// Initialize auth UI on page load
document.addEventListener('DOMContentLoaded', updateAuthUI);
