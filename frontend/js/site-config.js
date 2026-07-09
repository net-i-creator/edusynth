/**
 * Site-wide links and config (update when real URLs are ready).
 */
const SITE_CONFIG = {
    social: {
        vk: 'https://vk.com/umbaza',
        max: 'https://max.ru/umbaza',
    },
    extraLink: {
        label: 'О проекте',
        url: '#',
        enabled: false,
    },
    ministry: {
        text: 'Все уроки формируются в соответствии со стандартами Министерства образования Российской Федерации',
    },
};

const ROLE_LABELS = {
    student: 'Ученик',
    parent: 'Родитель',
    teacher: 'Преподаватель',
};

const EDUCATION_LEVEL_LABELS = {
    school: 'Школа',
    university: 'ВУЗ',
    extra: 'Доп. образование',
};

function applySiteLinks() {
    document.querySelectorAll('[data-link-vk]').forEach(el => {
        el.href = SITE_CONFIG.social.vk;
    });
    document.querySelectorAll('[data-link-max]').forEach(el => {
        el.href = SITE_CONFIG.social.max;
    });
    const extra = document.getElementById('extra-footer-link');
    if (extra && SITE_CONFIG.extraLink.enabled) {
        extra.href = SITE_CONFIG.extraLink.url;
        extra.textContent = SITE_CONFIG.extraLink.label;
        extra.classList.remove('hidden');
    }
}

document.addEventListener('DOMContentLoaded', applySiteLinks);
