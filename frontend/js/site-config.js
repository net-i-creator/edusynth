/**
 * Site-wide links and config (update when real URLs are ready).
 */
const SITE_CONFIG = {
    social: {
        vk: 'https://vk.com/UmBazaRF',
        max: 'https://max.ru/join/S42G2LXAaTZxptGMZhW8WdAO5-JMEpFv10IccQvNNsI',
    },
    payments: {
        yookassa: 'https://yookassa.ru/',
        sbp: 'https://sbp.nspk.ru/',
        tochka: 'https://tochka.com/',
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
    document.querySelectorAll('[data-link-yookassa]').forEach(el => {
        el.href = SITE_CONFIG.payments.yookassa;
    });
    document.querySelectorAll('[data-link-sbp]').forEach(el => {
        el.href = SITE_CONFIG.payments.sbp;
    });
    document.querySelectorAll('[data-link-tochka]').forEach(el => {
        el.href = SITE_CONFIG.payments.tochka;
    });
    const extra = document.getElementById('extra-footer-link');
    if (extra && SITE_CONFIG.extraLink.enabled) {
        extra.href = SITE_CONFIG.extraLink.url;
        extra.textContent = SITE_CONFIG.extraLink.label;
        extra.classList.remove('hidden');
    }
}

document.addEventListener('DOMContentLoaded', applySiteLinks);
