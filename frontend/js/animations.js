/**
 * GSAP Animations for УмБаза
 */

const GREETING_PHRASES = [
    'Приветствую!',
    'Я твой личный Преподаватель.',
    'Здесь Мы получаем знания.',
    'УмБаза',
    'Приступим.',
];

let greetingTimeline = null;
let selectedLevel = null;

document.addEventListener('DOMContentLoaded', () => {
    initHeroAnimations();
    initGreetingAnimation();
    initScrollAnimations();
    initOrbAnimations();
    initMagneticButtons();
});

function initHeroAnimations() {
    const tl = gsap.timeline({ defaults: { duration: 0.8, ease: 'power3.out' } });

    tl.to('.hero-badge', { opacity: 1, y: 0, delay: 0.2 })
      .to('.hero-greeting', { opacity: 1, y: 0 }, '-=0.5')
      .to('.hero-about', { opacity: 1, y: 0 }, '-=0.3')
      .to('.hero-steps', { opacity: 1, y: 0 }, '-=0.4')
      .to('.hero-levels', { opacity: 1, y: 0 }, '-=0.4');
}

function initGreetingAnimation() {
    const el = document.getElementById('greeting-text');
    if (!el) return;

    greetingTimeline = gsap.timeline({ repeat: -1, repeatDelay: 1.5, delay: 1.2 });

    GREETING_PHRASES.forEach((phrase, i) => {
        const isLast = i === GREETING_PHRASES.length - 1;
        const holdDuration = isLast ? 2.5 : 2;

        greetingTimeline
            .call(() => { el.textContent = phrase; })
            .fromTo(el,
                { opacity: 0, y: 16, filter: 'blur(6px)' },
                { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.7, ease: 'power2.out' }
            )
            .to(el, { opacity: 1, duration: holdDuration })
            .to(el,
                { opacity: 0, y: -12, filter: 'blur(4px)', duration: 0.5, ease: 'power2.in' },
                isLast ? '+=0' : '+=0'
            );
    });
}

function revealWorkspace(levelKey) {
    const config = EDUCATION_LEVELS[levelKey];
    if (!config || !config.enabled) return;

    selectedLevel = levelKey;

    document.querySelectorAll('.level-btn').forEach(btn => {
        btn.classList.remove('level-btn-active');
    });
    const activeBtn = document.getElementById(`level-${levelKey}`);
    if (activeBtn) activeBtn.classList.add('level-btn-active');

    populateFormFields(config);

    const label = document.getElementById('selected-level-label');
    if (label) label.textContent = config.label;

    const panel = document.getElementById('workspace-panel');
    if (!panel) return;

    panel.classList.add('is-visible');

    gsap.fromTo(panel,
        { opacity: 0, y: 32 },
        { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out' }
    );

    gsap.from('#gen-section .glass-strong', {
        scale: 0.97,
        opacity: 0,
        duration: 0.5,
        delay: 0.2,
        ease: 'power2.out',
    });

    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hideWorkspace() {
    selectedLevel = null;

    document.querySelectorAll('.level-btn').forEach(btn => {
        btn.classList.remove('level-btn-active');
    });

    const panel = document.getElementById('workspace-panel');
    if (!panel) return;

    gsap.to(panel, {
        opacity: 0,
        y: 20,
        duration: 0.4,
        ease: 'power2.in',
        onComplete: () => {
            panel.classList.remove('is-visible');
            gsap.set(panel, { opacity: 0, y: 0 });
        },
    });

    clearFormFields();
}

function populateFormFields(config) {
    const gradeSelect = document.getElementById('grade');
    const subjectSelect = document.getElementById('subject');
    const gradeLabel = document.getElementById('grade-label');

    if (gradeLabel) gradeLabel.textContent = config.gradeLabel;

    if (gradeSelect) {
        gradeSelect.innerHTML = '<option value="">Выберите</option>';
        config.grades.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g.value;
            opt.textContent = g.label;
            gradeSelect.appendChild(opt);
        });
    }

    if (subjectSelect) {
        subjectSelect.innerHTML = '<option value="">Выберите</option>';
        config.subjects.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = s;
            subjectSelect.appendChild(opt);
        });
    }
}

function clearFormFields() {
    const topic = document.getElementById('topic');
    const grade = document.getElementById('grade');
    const subject = document.getElementById('subject');
    if (topic) topic.value = '';
    if (grade) grade.value = '';
    if (subject) subject.value = '';
}

function initScrollAnimations() {
    gsap.utils.toArray('.step-card').forEach((card, i) => {
        gsap.to(card, {
            scrollTrigger: {
                trigger: card,
                start: 'top 85%',
                toggleActions: 'play none none none',
            },
            opacity: 1,
            y: 0,
            duration: 0.6,
            delay: i * 0.12,
            ease: 'power2.out',
        });
    });
}

function initOrbAnimations() {
    gsap.utils.toArray('.glass-orb').forEach((orb, i) => {
        gsap.to(orb, {
            y: `+=${20 + i * 8}`,
            x: `+=${10 + i * 5}`,
            duration: 6 + i * 1.5,
            repeat: -1,
            yoyo: true,
            ease: 'sine.inOut',
        });
    });

    gsap.utils.toArray('.glass-prism').forEach((prism, i) => {
        gsap.to(prism, {
            rotation: `+=${15 + i * 5}`,
            y: `+=${12 + i * 4}`,
            duration: 8 + i * 2,
            repeat: -1,
            yoyo: true,
            ease: 'sine.inOut',
        });
    });

    const spheres = ['#sphere-1', '#sphere-2', '#sphere-3'];
    const moves = [
        { x: 30, y: 20, duration: 9 },
        { x: -25, y: -30, duration: 11 },
        { x: 15, y: -20, duration: 13 },
    ];

    spheres.forEach((sel, i) => {
        const el = document.querySelector(sel);
        if (!el) return;
        gsap.to(el, { ...moves[i], repeat: -1, yoyo: true, ease: 'sine.inOut' });
    });
}

function animateLessonContent() {
    const tl = gsap.timeline({ defaults: { duration: 0.6, ease: 'power2.out' } });

    tl.from('.lesson-header', { opacity: 0, y: 20 })
      .from('.lesson-intro', { opacity: 0, y: 20 }, '-=0.3')
      .from('.lesson-main', { opacity: 0, y: 20 }, '-=0.3')
      .from('.lesson-gallery-wrap', { opacity: 0, y: 20 }, '-=0.3')
      .from('.lesson-examples', { opacity: 0, y: 20 }, '-=0.3')
      .from('.lesson-keypoints', { opacity: 0, y: 20 }, '-=0.3')
      .from('.lesson-quiz', { opacity: 0, y: 20 }, '-=0.3');
}

function animateQuizResult(scorePercent) {
    const resultEl = document.getElementById('quiz-result');
    if (!resultEl) return;

    gsap.from(resultEl, {
        scale: 0.8,
        opacity: 0,
        duration: 0.5,
        ease: 'back.out(1.7)',
    });

    const scoreEl = document.getElementById('score-value');
    const targetScore = typeof scorePercent === 'number' && !isNaN(scorePercent) ? Math.round(scorePercent) : 0;
    if (scoreEl) {
        const obj = { val: 0 };
        gsap.to(obj, {
            val: targetScore,
            duration: 1,
            ease: 'power1.out',
            onUpdate: function() {
                scoreEl.textContent = Math.round(obj.val) + '%';
            },
            onComplete: function() {
                scoreEl.textContent = targetScore + '%';
            },
        });
    }
}

function animateLoading() {
    const dots = document.querySelectorAll('.loading-dot');
    gsap.to(dots, {
        y: -10,
        duration: 0.4,
        stagger: 0.1,
        repeat: -1,
        yoyo: true,
        ease: 'power1.inOut',
    });
}

function initMagneticButtons() {
    document.querySelectorAll('.btn-magnetic').forEach(btn => {
        btn.addEventListener('mousemove', (e) => {
            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;

            gsap.to(btn, {
                x: x * 0.15,
                y: y * 0.15,
                duration: 0.3,
                ease: 'power2.out',
            });
        });

        btn.addEventListener('mouseleave', () => {
            gsap.to(btn, {
                x: 0,
                y: 0,
                duration: 0.5,
                ease: 'elastic.out(1, 0.3)',
            });
        });
    });
}
