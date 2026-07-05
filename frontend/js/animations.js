/**
 * GSAP Animations for УмБаза
 */

document.addEventListener('DOMContentLoaded', () => {
    initHeroAnimations();
    initScrollAnimations();
    initSphereAnimations();
    initMagneticButtons();
});

function initHeroAnimations() {
    const tl = gsap.timeline({ defaults: { duration: 0.8, ease: 'power3.out' } });

    tl.to('.hero-badge', { opacity: 1, y: 0, delay: 0.2 })
      .to('.hero-title', { opacity: 1, y: 0 }, '-=0.5')
      .to('.hero-subtitle', { opacity: 1, y: 0 }, '-=0.5')
      .to('.hero-about', { opacity: 1, y: 0 }, '-=0.4')
      .to('.hero-steps', { opacity: 1, y: 0 }, '-=0.4')
      .to('.hero-levels', { opacity: 1, y: 0 }, '-=0.4')
      .to('.hero-form', { opacity: 1, y: 0 }, '-=0.4');
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

function initSphereAnimations() {
    gsap.to('#sphere-1', {
        x: 40,
        y: 30,
        duration: 8,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
    });

    gsap.to('#sphere-2', {
        x: -30,
        y: -40,
        duration: 10,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
    });

    gsap.to('#sphere-3', {
        x: 20,
        y: -25,
        duration: 12,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
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
