/**
 * Arena Mission Map — Dynamic Arrow Engine
 * Draws glowing SVG arrows between mission nodes,
 * handles hover interactions and responsive recalculation.
 */
(function () {
    'use strict';

    const ARROW_COLORS = {
        completed: { stroke: '#10b981', glow: 'rgba(16, 185, 129, 0.6)' },
        active: { stroke: '#64ffda', glow: 'rgba(100, 255, 218, 0.6)' },
        locked: { stroke: 'rgba(136, 146, 176, 0.2)', glow: 'none' }
    };

    /**
     * Determine the arrow status between two nodes.
     * Arrow gets the status of the "from" node (source determines glow).
     */
    function getArrowStatus(fromNode) {
        if (fromNode.classList.contains('completed')) return 'completed';
        if (fromNode.classList.contains('unlocked') || fromNode.classList.contains('available')) return 'active';
        return 'locked';
    }

    /**
     * Draw CSS-based arrows (already in HTML).
     * Update their status classes to match node states.
     */
    function updateArrowStates() {
        const steps = document.querySelectorAll('.mission-step');
        const arrows = document.querySelectorAll('.mission-arrow');

        arrows.forEach((arrow, i) => {
            // Arrow i connects step i to step i+1
            const fromStep = steps[i];
            if (!fromStep) return;

            const fromNode = fromStep.querySelector('.mission-node');
            if (!fromNode) return;

            const status = getArrowStatus(fromNode);

            arrow.classList.remove('active', 'completed', 'locked');
            arrow.classList.add(status);
        });
    }

    /**
     * Setup hover interactions:
     * - Hovering a step highlights it, its outgoing arrow, and the next node
     */
    function setupHoverEffects() {
        const steps = document.querySelectorAll('.mission-step');

        steps.forEach((step, i) => {
            const node = step.querySelector('.mission-node');
            if (!node || node.classList.contains('locked')) return;

            step.addEventListener('mouseenter', () => {
                // Highlight next arrow
                const nextArrow = document.querySelectorAll('.mission-arrow')[i];
                if (nextArrow) {
                    nextArrow.classList.add('hover-highlight');
                }

                // Highlight next node
                const nextStep = steps[i + 1];
                if (nextStep) {
                    const nextNode = nextStep.querySelector('.mission-node');
                    if (nextNode) nextNode.classList.add('hover-peer');
                }
            });

            step.addEventListener('mouseleave', () => {
                // Remove highlights
                const nextArrow = document.querySelectorAll('.mission-arrow')[i];
                if (nextArrow) {
                    nextArrow.classList.remove('hover-highlight');
                }

                const nextStep = steps[i + 1];
                if (nextStep) {
                    const nextNode = nextStep.querySelector('.mission-node');
                    if (nextNode) nextNode.classList.remove('hover-peer');
                }
            });
        });
    }

    /**
     * Add dynamic CSS for hover peer highlighting
     */
    function injectDynamicStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .mission-arrow.hover-highlight .arrow-line {
                filter: brightness(1.8) !important;
                transform: scaleX(1.4);
            }
            .mission-arrow.hover-highlight .arrow-head {
                filter: brightness(1.8) !important;
                transform: scale(1.3);
            }
            .mission-node.hover-peer:not(.locked) {
                transform: scale(1.08);
                filter: brightness(1.2);
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Initialize on DOMContentLoaded
     */
    document.addEventListener('DOMContentLoaded', () => {
        updateArrowStates();
        setupHoverEffects();
        injectDynamicStyles();
    });

    // Recalculate on resize (arrow states stay CSS-based, so this is lightweight)
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(updateArrowStates, 150);
    });

})();
