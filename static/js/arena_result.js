/* Arena Result Page JS */
document.addEventListener('DOMContentLoaded', function () {
    // Animate XP pop
    const xpEl = document.querySelector('.xp-plus');
    if (xpEl) {
        xpEl.style.animation = 'xpPop 0.6s ease forwards';
    }
    // Animate XP bar fill
    const xpFill = document.querySelector('.arena-xp-fill');
    if (xpFill) {
        const w = xpFill.style.width;
        xpFill.style.width = '0%';
        setTimeout(() => { xpFill.style.width = w; }, 300);
    }
});
