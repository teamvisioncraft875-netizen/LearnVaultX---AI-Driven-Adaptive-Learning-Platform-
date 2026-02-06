// ============================================
// ANIMATED DASHBOARD STATS
// Count-up animations with viewport detection
// ============================================

class AnimatedCounter {
    constructor(element, target, duration = 2000) {
        this.element = element;
        this.target = parseFloat(target);
        this.duration = duration;
        this.hasAnimated = false;
    }

    animate() {
        if (this.hasAnimated) return;
        this.hasAnimated = true;

        const start = 0;
        const startTime = performance.now();
        const isPercentage = this.element.textContent.includes('%');
        const isDecimal = this.target % 1 !== 0;

        const updateCounter = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / this.duration, 1);
            
            // Easing function (easeOutCubic)
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = start + (this.target - start) * eased;
            
            if (isDecimal) {
                this.element.textContent = current.toFixed(1) + (isPercentage ? '%' : '');
            } else {
                this.element.textContent = Math.floor(current) + (isPercentage ? '%' : '');
            }

            if (progress < 1) {
                requestAnimationFrame(updateCounter);
            } else {
                this.element.textContent = this.target + (isPercentage ? '%' : '');
            }
        };

        requestAnimationFrame(updateCounter);
    }
}

// Viewport observer for triggering animations
const observeCounters = () => {
    const counters = document.querySelectorAll('[data-animate-counter]');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const target = entry.target.dataset.animateCounter;
                const duration = parseInt(entry.target.dataset.animateDuration) || 2000;
                const counter = new AnimatedCounter(entry.target, target, duration);
                counter.animate();
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => observer.observe(counter));
};

// ============================================
// MICRO-INTERACTIONS
// Button ripple, card tilt, smooth transitions
// ============================================

// Button ripple effect
const addRippleEffect = () => {
    document.addEventListener('click', (e) => {
        const button = e.target.closest('button, .btn, .card-interactive');
        if (!button) return;

        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;

        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            left: ${x}px;
            top: ${y}px;
            pointer-events: none;
            transform: scale(0);
            animation: ripple 0.6s ease-out;
        `;

        button.style.position = 'relative';
        button.style.overflow = 'hidden';
        button.appendChild(ripple);

        setTimeout(() => ripple.remove(), 600);
    });
};

// Card 3D tilt effect
const addCardTilt = () => {
    const cards = document.querySelectorAll('.card, .metric-card, .feature-card');
    
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            if (document.body.classList.contains('reduce-motion')) return;
            
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateX = (y - centerY) / 20;
            const rotateY = (centerX - x) / 20;
            
            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });
};

// ============================================
// SMART NOTIFICATIONS SYSTEM
// Toast notifications with auto-dismiss
// ============================================

class NotificationSystem {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        if (!document.getElementById('notification-container')) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 12px;
                pointer-events: none;
            `;
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('notification-container');
        }
    }

    show(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        toast.innerHTML = `
            <span class="toast-icon">${icons[type]}</span>
            <span class="toast-message">${message}</span>
        `;

        toast.style.cssText = `
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            pointer-events: all;
            animation: slideInRight 0.3s ease-out;
            min-width: 300px;
            max-width: 400px;
        `;

        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#60a5fa'
        };

        toast.style.borderLeftColor = colors[type];
        toast.style.borderLeftWidth = '4px';

        this.container.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    success(message) { this.show(message, 'success'); }
    error(message) { this.show(message, 'error'); }
    warning(message) { this.show(message, 'warning'); }
    info(message) { this.show(message, 'info'); }
}

// Global notification instance
window.notify = new NotificationSystem();

// ============================================
// KEYBOARD SHORTCUTS
// Command palette and global shortcuts
// ============================================

class KeyboardShortcuts {
    constructor() {
        this.shortcuts = {
            'ctrl+k': () => this.openCommandPalette(),
            'ctrl+/': () => this.toggleAIPanel(),
            'ctrl+t': () => this.cycleTheme(),
            'escape': () => this.closeModals()
        };
        this.init();
    }

    init() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger if typing in input
            if (e.target.matches('input, textarea, [contenteditable]')) return;

            const key = this.getKeyCombo(e);
            if (this.shortcuts[key]) {
                e.preventDefault();
                this.shortcuts[key]();
            }
        });
    }

    getKeyCombo(e) {
        const parts = [];
        if (e.ctrlKey || e.metaKey) parts.push('ctrl');
        if (e.shiftKey) parts.push('shift');
        if (e.altKey) parts.push('alt');
        
        const key = e.key.toLowerCase();
        if (!['control', 'shift', 'alt', 'meta'].includes(key)) {
            parts.push(key);
        }
        
        return parts.join('+');
    }

    openCommandPalette() {
        // Create command palette if doesn't exist
        let palette = document.getElementById('command-palette');
        if (!palette) {
            palette = this.createCommandPalette();
        }
        palette.classList.add('active');
        palette.querySelector('input')?.focus();
    }

    createCommandPalette() {
        const palette = document.createElement('div');
        palette.id = 'command-palette';
        palette.className = 'command-palette';
        palette.innerHTML = `
            <div class="command-palette-content">
                <input type="text" placeholder="Type a command..." class="command-input">
                <div class="command-list">
                    <div class="command-item" data-action="toggle-ai">
                        <span>Toggle AI Panel</span>
                        <kbd>Ctrl+/</kbd>
                    </div>
                    <div class="command-item" data-action="toggle-theme">
                        <span>Change Theme</span>
                        <kbd>Ctrl+T</kbd>
                    </div>
                    <div class="command-item" data-action="settings">
                        <span>Open Settings</span>
                        <kbd>⚙️</kbd>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(palette);
        
        // Event listeners
        palette.addEventListener('click', (e) => {
            if (e.target === palette) palette.classList.remove('active');
            
            const item = e.target.closest('.command-item');
            if (item) {
                const action = item.dataset.action;
                this.executeCommand(action);
                palette.classList.remove('active');
            }
        });

        return palette;
    }

    executeCommand(action) {
        const actions = {
            'toggle-ai': () => this.toggleAIPanel(),
            'toggle-theme': () => this.cycleTheme(),
            'settings': () => document.getElementById('settingsBtn')?.click()
        };
        actions[action]?.();
    }

    toggleAIPanel() {
        const aiPanel = document.getElementById('ai-panel') || document.getElementById('classAI');
        if (aiPanel) {
            const toggleBtn = document.querySelector('[onclick*="toggleAI"]');
            toggleBtn?.click();
        }
    }

    cycleTheme() {
        const themeBtn = document.getElementById('themeToggle');
        themeBtn?.click();
    }

    closeModals() {
        // Close all modals
        document.querySelectorAll('.modal.active, .settings-modal.active, .command-palette.active').forEach(modal => {
            modal.classList.remove('active');
        });
    }
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Check for reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        document.body.classList.add('reduce-motion');
    }

    // Initialize features
    observeCounters();
    addRippleEffect();
    addCardTilt();
    new KeyboardShortcuts();

    // Add CSS animations
    if (!document.getElementById('premium-animations')) {
        const style = document.createElement('style');
        style.id = 'premium-animations';
        style.textContent = `
            @keyframes ripple {
                to {
                    transform: scale(4);
                    opacity: 0;
                }
            }

            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }

            @keyframes slideOutRight {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }

            .command-palette {
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(8px);
                z-index: 10000;
                display: none;
                align-items: flex-start;
                justify-content: center;
                padding-top: 20vh;
            }

            .command-palette.active {
                display: flex;
            }

            .command-palette-content {
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                width: 90%;
                max-width: 600px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                overflow: hidden;
            }

            .command-input {
                width: 100%;
                padding: 20px 24px;
                background: transparent;
                border: none;
                border-bottom: 1px solid var(--border-color);
                color: var(--text-primary);
                font-size: 18px;
                outline: none;
            }

            .command-list {
                max-height: 400px;
                overflow-y: auto;
            }

            .command-item {
                padding: 16px 24px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                cursor: pointer;
                transition: background 0.2s;
            }

            .command-item:hover {
                background: var(--bg-tertiary);
            }

            .command-item kbd {
                background: var(--bg-tertiary);
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 12px;
                font-family: monospace;
            }

            .toast-icon {
                font-size: 20px;
            }

            .toast-message {
                color: var(--text-primary);
                font-size: 14px;
                font-weight: 500;
            }

            body.reduce-motion * {
                animation-duration: 0.01ms !important;
                transition-duration: 0.01ms !important;
            }
        `;
        document.head.appendChild(style);
    }
});

// Export for use in other scripts
window.AnimatedCounter = AnimatedCounter;
window.observeCounters = observeCounters;
