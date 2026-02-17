/**
 * Toast Notification System for LearnVaultX
 * Provides glowing, animated toast notifications
 * Usage: showToast(message, type, title)
 */

(function() {
    // Create toast container if it doesn't exist
    function initToastContainer() {
        if (!document.getElementById('toast-container')) {
            const container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
    }

    /**
     * Show a toast notification
     * @param {string} message - The message to display
     * @param {string} type - Type of toast: 'success', 'error', 'warning', 'info'
     * @param {string} title - Optional title for the toast
     * @param {number} duration - Duration in milliseconds (default: 3000)
     */
    window.showToast = function(message, type = 'info', title = null, duration = 3000) {
        initToastContainer();
        
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        // Icon mapping
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        
        // Title mapping
        const titles = {
            success: title || 'Success',
            error: title || 'Error',
            warning: title || 'Warning',
            info: title || 'Info'
        };
        
        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-content">
                <div class="toast-title">${titles[type]}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" onclick="this.closest('.toast').remove()">×</button>
            <div class="toast-progress"></div>
        `;
        
        container.appendChild(toast);
        
        // Auto-dismiss
        setTimeout(() => {
            toast.classList.add('removing');
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.remove();
                }
            }, 300);
        }, duration);
        
        // Return toast element for programmatic control
        return toast;
    };

    /**
     * Quick success toast
     */
    window.toastSuccess = function(message, title) {
        return showToast(message, 'success', title);
    };

    /**
     * Quick error toast
     */
    window.toastError = function(message, title) {
        return showToast(message, 'error', title);
    };

    /**
     * Quick warning toast
     */
    window.toastWarning = function(message, title) {
        return showToast(message, 'warning', title);
    };

    /**
     * Quick info toast
     */
    window.toastInfo = function(message, title) {
        return showToast(message, 'info', title);
    };

    /**
     * Replace all alert() calls with toasts
     */
    window.originalAlert = window.alert;
    window.alert = function(message) {
        showToast(message, 'info', 'Alert');
    };

    // Initialize container on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initToastContainer);
    } else {
        initToastContainer();
    }
})();
