/**
 * Guest lesson limit: 1 free generation without registration.
 */
const GUEST_LESSON_KEY = 'guest_lessons_count';
const GUEST_ID_KEY = 'guest_id';
const GUEST_LESSON_LIMIT = 1;

function getGuestId() {
    let id = localStorage.getItem(GUEST_ID_KEY);
    if (!id) {
        id = typeof crypto !== 'undefined' && crypto.randomUUID
            ? crypto.randomUUID()
            : 'guest-' + Date.now() + '-' + Math.random().toString(36).slice(2);
        localStorage.setItem(GUEST_ID_KEY, id);
    }
    return id;
}

function getGuestLessonCount() {
    return parseInt(localStorage.getItem(GUEST_LESSON_KEY) || '0', 10);
}

function incrementGuestLessonCount() {
    const count = getGuestLessonCount() + 1;
    localStorage.setItem(GUEST_LESSON_KEY, String(count));
    return count;
}

function canGenerateAsGuest() {
    if (typeof isLoggedIn === 'function' && isLoggedIn()) return true;
    return getGuestLessonCount() < GUEST_LESSON_LIMIT;
}

function requireAuthForGeneration() {
    if (canGenerateAsGuest()) return true;

    const redirect = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `auth.html?reason=limit&redirect=${redirect}`;
    return false;
}

function onLessonGenerated() {
    if (typeof isLoggedIn === 'function' && isLoggedIn()) return;
    incrementGuestLessonCount();
}

function getGuestRemainingText() {
    if (typeof isLoggedIn === 'function' && isLoggedIn()) return null;
    const remaining = GUEST_LESSON_LIMIT - getGuestLessonCount();
    if (remaining <= 0) return 'Бесплатный урок использован — войдите для продолжения';
    if (remaining === 1) return '1 бесплатный урок без регистрации';
    return null;
}

function handleGuestLimitError(error) {
    if (error && error.message && error.message.includes('Guest limit')) {
        const redirect = encodeURIComponent(window.location.pathname);
        window.location.href = `auth.html?reason=limit&redirect=${redirect}`;
        return true;
    }
    return false;
}
