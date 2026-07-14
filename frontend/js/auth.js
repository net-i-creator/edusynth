/**
 * Auth utilities
 */

let _siteConfig = null;
let _siteConfigPromise = null;

async function loadSiteConfig() {
    if (_siteConfig) return _siteConfig;
    if (!_siteConfigPromise) {
        _siteConfigPromise = api.getSiteConfig()
            .then((cfg) => {
                _siteConfig = cfg;
                return cfg;
            })
            .catch(() => {
                _siteConfig = { auth_enabled: true };
                return _siteConfig;
            });
    }
    return _siteConfigPromise;
}

function isAuthEnabled() {
    if (_siteConfig) return _siteConfig.auth_enabled !== false;
    return true;
}

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
    } else if (isAuthEnabled()) {
        authButtons.classList.remove('hidden');
        userMenu.classList.add('hidden');
    } else {
        authButtons.classList.add('hidden');
        userMenu.classList.add('hidden');
    }
}

async function applyAuthVisibility() {
    await loadSiteConfig();
    if (isAuthEnabled()) return;

    document.querySelectorAll('[data-auth-only]').forEach((el) => el.classList.add('hidden'));

    const navAccount = document.getElementById('nav-account');
    if (navAccount && !isLoggedIn()) {
        navAccount.classList.add('hidden');
    }
}

// Initialize auth UI on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadSiteConfig();
    updateAuthUI();
    applyAuthVisibility();
});
