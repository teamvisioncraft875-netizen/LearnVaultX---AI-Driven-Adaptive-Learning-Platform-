// ============================================
// ONBOARDING TOUR SYSTEM
// First-time user walkthrough
// ============================================

class OnboardingTour {
    constructor() {
        this.steps = [
            {
                target: '.left-zone, .sidebar',
                title: 'Navigation Sidebar',
                description: 'Access all your classes, dashboard, and settings from here.',
                position: 'right'
            },
            {
                target: '#ai-panel, #classAI',
                title: 'AI Assistant',
                description: 'Get instant help from our AI tutor. Ask questions, get explanations, and more!',
                position: 'left'
            },
            {
                target: '.metrics-grid, .overview-metrics',
                title: 'Your Progress',
                description: 'Track your learning progress, quiz scores, and achievements.',
                position: 'bottom'
            },
            {
                target: '#settingsBtn',
                title: 'Settings',
                description: 'Customize your experience: themes, AI preferences, and more.',
                position: 'left'
            }
        ];
        this.currentStep = 0;
        this.hasCompleted = localStorage.getItem('onboarding_completed') === 'true';
    }

    start() {
        if (this.hasCompleted) return;

        this.createOverlay();
        this.showStep(0);
    }

    createOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'onboarding-overlay';
        overlay.className = 'onboarding-overlay';
        document.body.appendChild(overlay);
    }

    showStep(index) {
        if (index >= this.steps.length) {
            this.complete();
            return;
        }

        this.currentStep = index;
        const step = this.steps[index];
        const target = document.querySelector(step.target);

        if (!target) {
            this.showStep(index + 1);
            return;
        }

        // Highlight target
        target.classList.add('onboarding-highlight');

        // Create tooltip
        const tooltip = this.createTooltip(step, index);
        this.positionTooltip(tooltip, target, step.position);

        document.body.appendChild(tooltip);
    }

    createTooltip(step, index) {
        const tooltip = document.createElement('div');
        tooltip.className = 'onboarding-tooltip';
        tooltip.innerHTML = `
            <div class="onboarding-tooltip-header">
                <h3>${step.title}</h3>
                <span class="onboarding-step-count">${index + 1}/${this.steps.length}</span>
            </div>
            <p>${step.description}</p>
            <div class="onboarding-tooltip-actions">
                <button class="btn-onboarding-skip" onclick="window.onboardingTour.skip()">Skip</button>
                <button class="btn-onboarding-next" onclick="window.onboardingTour.next()">
                    ${index === this.steps.length - 1 ? 'Finish' : 'Next'}
                </button>
            </div>
        `;
        return tooltip;
    }

    positionTooltip(tooltip, target, position) {
        const rect = target.getBoundingClientRect();
        tooltip.style.position = 'fixed';
        tooltip.style.zIndex = '10001';

        const positions = {
            right: () => {
                tooltip.style.left = rect.right + 20 + 'px';
                tooltip.style.top = rect.top + 'px';
            },
            left: () => {
                tooltip.style.right = window.innerWidth - rect.left + 20 + 'px';
                tooltip.style.top = rect.top + 'px';
            },
            bottom: () => {
                tooltip.style.left = rect.left + 'px';
                tooltip.style.top = rect.bottom + 20 + 'px';
            },
            top: () => {
                tooltip.style.left = rect.left + 'px';
                tooltip.style.bottom = window.innerHeight - rect.top + 20 + 'px';
            }
        };

        positions[position]?.();
    }

    next() {
        this.cleanup();
        this.showStep(this.currentStep + 1);
    }

    skip() {
        this.cleanup();
        this.complete();
    }

    cleanup() {
        document.querySelectorAll('.onboarding-highlight').forEach(el => {
            el.classList.remove('onboarding-highlight');
        });
        document.querySelectorAll('.onboarding-tooltip').forEach(el => {
            el.remove();
        });
    }

    complete() {
        this.cleanup();
        const overlay = document.getElementById('onboarding-overlay');
        if (overlay) overlay.remove();

        localStorage.setItem('onboarding_completed', 'true');
        this.hasCompleted = true;

        window.notify?.success('Welcome to LearnVaultX! 🎉');
    }
}

// ============================================
// INITIALIZE ON LOAD
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Onboarding (disabled auto-start to prevent page darkening)
    window.onboardingTour = new OnboardingTour();
    // Uncomment below to enable auto-start for first-time users:
    // setTimeout(() => {
    //     if (!window.onboardingTour.hasCompleted) {
    //         window.onboardingTour.start();
    //     }
    // }, 1000);

    // Add onboarding styles
    if (!document.getElementById('onboarding-styles')) {
        const style = document.createElement('style');
        style.id = 'onboarding-styles';
        style.textContent = `
            /* Onboarding Styles */
            .onboarding-overlay {
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.7);
                z-index: 10000;
            }

            .onboarding-highlight {
                position: relative;
                z-index: 10001;
                box-shadow: 0 0 0 4px var(--primary), 0 0 0 8px rgba(96, 165, 250, 0.3);
                border-radius: 12px;
            }

            .onboarding-tooltip {
                background: var(--bg-secondary);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 20px;
                max-width: 320px;
                box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
            }

            .onboarding-tooltip-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }

            .onboarding-tooltip-header h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 600;
            }

            .onboarding-step-count {
                font-size: 12px;
                color: var(--text-tertiary);
            }

            .onboarding-tooltip p {
                margin: 0 0 16px 0;
                color: var(--text-secondary);
                line-height: 1.5;
            }

            .onboarding-tooltip-actions {
                display: flex;
                gap: 8px;
            }

            .btn-onboarding-skip,
            .btn-onboarding-next {
                flex: 1;
                padding: 10px 16px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }

            .btn-onboarding-skip {
                background: transparent;
                border: 1px solid var(--border-color);
                color: var(--text-secondary);
            }

            .btn-onboarding-next {
                background: linear-gradient(135deg, #ec4899, #8b5cf6);
                border: none;
                color: white;
            }
        `;
        document.head.appendChild(style);
    }
});
