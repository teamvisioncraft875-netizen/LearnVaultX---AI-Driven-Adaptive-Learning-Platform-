(function () {
    'use strict';

    const STORAGE_KEY = 'sidebarCollapsed';
    const MOBILE_BREAKPOINT = 960;

    function getSidebar() {
        return document.querySelector('.stud-sidebar, .dash-sidebar, .class-sidebar');
    }

    function getOverlay() {
        return document.querySelector('.stud-overlay, .dash-overlay, .overlay');
    }

    function isMobile() {
        return window.innerWidth <= MOBILE_BREAKPOINT;
    }

    function applyCollapsedState(sidebar) {
        if (!sidebar || isMobile()) return;
        const collapsed = localStorage.getItem(STORAGE_KEY) === 'true';
        sidebar.classList.toggle('collapsed', collapsed);
        document.body.classList.toggle('sidebar-collapsed', collapsed);
    }

    function toggleDesktopSidebar() {
        const sidebar = getSidebar();
        if (!sidebar || isMobile()) return;
        const collapsed = sidebar.classList.toggle('collapsed');
        document.body.classList.toggle('sidebar-collapsed', collapsed);
        localStorage.setItem(STORAGE_KEY, collapsed ? 'true' : 'false');
    }

    function toggleMobileSidebar() {
        const sidebar = getSidebar();
        const overlay = getOverlay();
        if (!sidebar) return;
        const openClass = sidebar.classList.contains('mobile-show') ? 'mobile-show' : 'active';
        const willOpen = !sidebar.classList.contains(openClass);
        sidebar.classList.toggle(openClass, willOpen);
        sidebar.classList.toggle('mobile-open', willOpen);
        if (overlay) {
            overlay.classList.toggle('show', willOpen);
            overlay.classList.toggle('active', willOpen);
            overlay.style.display = willOpen ? 'block' : '';
        }
    }

    function ensureToggleButton() {
        const sidebar = getSidebar();
        if (!sidebar) return;
        let btn = document.querySelector('.sidebar-toggle');
        if (!btn) {
            btn = document.createElement('button');
            btn.className = 'sidebar-toggle';
            btn.type = 'button';
            btn.setAttribute('aria-label', 'Toggle sidebar');
            btn.innerHTML = '☰';
            document.body.appendChild(btn);
        }
        btn.onclick = () => {
            if (isMobile()) {
                toggleMobileSidebar();
            } else {
                toggleDesktopSidebar();
            }
        };
    }

    function wireOverlays() {
        const overlay = getOverlay();
        if (!overlay || overlay.dataset.sidebarBound === 'true') return;
        overlay.dataset.sidebarBound = 'true';
        overlay.addEventListener('click', () => {
            const sidebar = getSidebar();
            if (!sidebar) return;
            sidebar.classList.remove('mobile-show', 'active', 'mobile-open');
            overlay.classList.remove('show', 'active');
            overlay.style.display = '';
            document.body.classList.remove('sidebar-mobile-open');
        });
    }

    function handleResponsive() {
        const sidebar = getSidebar();
        if (!sidebar) return;
        if (isMobile()) {
            sidebar.classList.remove('collapsed');
            document.body.classList.remove('sidebar-collapsed');
        } else {
            sidebar.classList.remove('mobile-show', 'active', 'mobile-open');
            const overlay = getOverlay();
            if (overlay) {
                overlay.classList.remove('show', 'active');
                overlay.style.display = '';
            }
            applyCollapsedState(sidebar);
        }
    }

    // Expose shared mobile toggle for templates
    window.toggleMobileSidebar = toggleMobileSidebar;

    function init() {
        if (!getSidebar()) return;
        ensureToggleButton();
        wireOverlays();
        applyCollapsedState(getSidebar());
        handleResponsive();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(handleResponsive, 200);
    });
})();
