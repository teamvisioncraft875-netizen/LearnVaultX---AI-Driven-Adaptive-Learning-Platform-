// ============================================
// PANEL MANAGEMENT SYSTEM
// IDE-style panel toggling (VS Code inspired)
// ============================================

class PanelManager {
    constructor() {
        this.activePanel = null;
        this.panels = {
            ai: null,
            settings: null
        };
        this.init();
    }

    init() {
        // Find panels
        this.panels.ai = document.getElementById('ai-panel') || document.getElementById('classAI');
        this.panels.settings = document.getElementById('settingsModal');

        // Attach event listeners
        this.attachListeners();
    }

    attachListeners() {
        // AI Toggle Button
        const aiToggleBtn = document.querySelector('[data-panel="ai"]');
        if (aiToggleBtn) {
            aiToggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggle('ai');
            });
        }

        // Settings Toggle Button
        const settingsBtn = document.getElementById('settingsBtn');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggle('settings');
            });
        }

        // Close buttons
        this.attachCloseButtons();
    }

    attachCloseButtons() {
        // AI Panel close
        if (this.panels.ai) {
            const closeBtn = this.panels.ai.querySelector('.close-panel, .panel-close, [data-action="close"]');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.close('ai'));
            }
        }

        // Settings Panel close
        if (this.panels.settings) {
            const closeBtn = this.panels.settings.querySelector('.settings-close, #settingsClose');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.close('settings'));
            }

            // Click outside to close
            this.panels.settings.addEventListener('click', (e) => {
                if (e.target === this.panels.settings) {
                    this.close('settings');
                }
            });
        }
    }

    toggle(panelName) {
        if (this.activePanel === panelName) {
            // Close if already open
            this.close(panelName);
        } else {
            // Close any open panel first
            if (this.activePanel) {
                this.close(this.activePanel);
            }
            // Open new panel
            this.open(panelName);
        }
    }

    open(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        // Mark as active
        this.activePanel = panelName;

        // Add active class
        panel.classList.add('active');

        // Update center content width
        this.updateCenterContent(true);

        // Update button states
        this.updateButtonStates();
    }

    close(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        // Remove active class
        panel.classList.remove('active');

        // Clear active panel
        if (this.activePanel === panelName) {
            this.activePanel = null;
        }

        // Update center content width
        this.updateCenterContent(false);

        // Update button states
        this.updateButtonStates();
    }

    updateCenterContent(panelOpen) {
        const centerContent = document.querySelector('.center-zone, .center-content, .main-content');
        if (!centerContent) return;

        if (panelOpen) {
            centerContent.style.marginRight = '400px'; // Panel width
        } else {
            centerContent.style.marginRight = '0';
        }
    }

    updateButtonStates() {
        // Update AI button
        const aiBtn = document.querySelector('[data-panel="ai"]');
        if (aiBtn) {
            if (this.activePanel === 'ai') {
                aiBtn.classList.add('active');
            } else {
                aiBtn.classList.remove('active');
            }
        }

        // Update History button
        const historyBtn = document.querySelector('[data-panel="history"]');
        if (historyBtn) {
            if (this.activePanel === 'history') {
                historyBtn.classList.add('active');
            } else {
                historyBtn.classList.remove('active');
            }
        }
    }
}

// ============================================
// FIXED FLOATING BUTTONS
// Stable positioning, no drift
// ============================================

function initializeFloatingButtons() {
    // Create container for floating buttons
    let fabContainer = document.getElementById('fab-container');

    if (!fabContainer) {
        fabContainer = document.createElement('div');
        fabContainer.id = 'fab-container';
        fabContainer.className = 'fab-container';
        document.body.appendChild(fabContainer);
    }

    // Move theme toggle to container (if exists)
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.remove(); // Remove standalone theme toggle
    }

    // Create Settings button if doesn't exist
    let settingsBtn = document.getElementById('settingsBtn');
    if (!settingsBtn) {
        settingsBtn = document.createElement('button');
        settingsBtn.id = 'settingsBtn';
        settingsBtn.className = 'fab-button settings-fab';
        settingsBtn.setAttribute('aria-label', 'Open settings');
        settingsBtn.setAttribute('title', 'Settings');
        settingsBtn.innerHTML = '⚙️';
        fabContainer.appendChild(settingsBtn);
    } else if (!fabContainer.contains(settingsBtn)) {
        fabContainer.appendChild(settingsBtn);
    }

    // Add styles
    addFloatingButtonStyles();
}

function addFloatingButtonStyles() {
    if (document.getElementById('fab-styles')) return;

    const style = document.createElement('style');
    style.id = 'fab-styles';
    style.textContent = `
        /* Fixed Floating Button Container */
        .fab-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            z-index: 999;
            pointer-events: none;
        }

        .fab-container > * {
            pointer-events: all;
        }

        /* Base FAB Button Style */
        .fab-button {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, #ec4899, #8b5cf6);
            color: white;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .fab-button:hover {
            transform: scale(1.1);
            box-shadow: 0 6px 20px rgba(236, 72, 153, 0.5);
        }

        .fab-button.active {
            background: linear-gradient(135deg, #10b981, #059669);
        }

        /* AI Toggle FAB */
        .ai-toggle-fab {
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
        }

        .ai-toggle-fab:hover {
            box-shadow: 0 6px 20px rgba(96, 165, 250, 0.5);
        }

        /* Settings FAB */
        .settings-fab {
            background: linear-gradient(135deg, #ec4899, #8b5cf6);
        }

        /* Mobile Adjustments */
        @media (max-width: 768px) {
            .fab-container {
                bottom: 16px;
                right: 16px;
                gap: 12px;
            }

            .fab-button {
                width: 48px;
                height: 48px;
                font-size: 20px;
            }
        }

        /* Panel Slide Animations */
        .active.slide-panel {
            animation: slideInRight 0.3s ease-out forwards;
        }

        .slide-panel:not(.active) {
            animation: slideOutRight 0.3s ease-out forwards;
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

        /* Center Content Transition */
        .center-zone,
        .center-content,
        .main-content {
            transition: margin-right 0.3s ease;
        }
    `;
    document.head.appendChild(style);
}

// ============================================
// ACCOUNT SETTINGS SECTION
// ============================================

function addAccountSettingsToPanel() {
    const settingsBody = document.querySelector('.settings-body');
    if (!settingsBody) return;

    // Check if already exists
    if (document.getElementById('account-settings-section')) return;

    const accountSection = document.createElement('div');
    accountSection.id = 'account-settings-section';
    accountSection.className = 'settings-section';
    accountSection.innerHTML = `
        <h3 class="settings-section-title">Account Settings</h3>
        
        <div class="setting-item">
            <label for="userName">Name</label>
            <input type="text" id="userName" class="setting-input" placeholder="Your name">
        </div>

        <div class="setting-item">
            <label for="userEmail">Email</label>
            <input type="email" id="userEmail" class="setting-input" placeholder="your@email.com" readonly>
        </div>

        <div class="setting-item">
            <label for="changePassword">Change Password</label>
            <button class="setting-button" id="changePasswordBtn">Change Password</button>
        </div>

        <div class="setting-item setting-danger-zone">
            <label>Danger Zone</label>
            <button class="setting-button setting-button-danger" id="logoutBtn">Logout</button>
            <button class="setting-button setting-button-danger" id="deleteAccountBtn">Delete Account</button>
        </div>
    `;

    // Insert at the beginning
    settingsBody.insertBefore(accountSection, settingsBody.firstChild);

    // Add event listeners
    attachAccountSettingsListeners();

    // Add styles
    addAccountSettingsStyles();
}

function attachAccountSettingsListeners() {
    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to logout?')) {
                window.location.href = '/logout';
            }
        });
    }

    // Delete Account
    const deleteBtn = document.getElementById('deleteAccountBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', () => {
            const confirmed = confirm('⚠️ WARNING: This will permanently delete your account and all data. This action cannot be undone.\n\nType "DELETE" to confirm:');
            if (confirmed) {
                const verification = prompt('Type DELETE to confirm account deletion:');
                if (verification === 'DELETE') {
                    // Call delete API
                    window.notify?.warning('Account deletion feature coming soon');
                }
            }
        });
    }

    // Change Password
    const changePasswordBtn = document.getElementById('changePasswordBtn');
    if (changePasswordBtn) {
        changePasswordBtn.addEventListener('click', () => {
            window.notify?.info('Password change feature coming soon');
        });
    }

    // Load user data
    loadUserData();
}

function loadUserData() {
    // Try to get user data from API
    fetch('/api/user/data')
        .then(res => res.json())
        .then(data => {
            const nameInput = document.getElementById('userName');
            const emailInput = document.getElementById('userEmail');

            if (nameInput && data.name) {
                nameInput.value = data.name;
            }
            if (emailInput && data.email) {
                emailInput.value = data.email;
            }
        })
        .catch(err => {
            console.error('Failed to load user data:', err);
        });
}

function addAccountSettingsStyles() {
    if (document.getElementById('account-settings-styles')) return;

    const style = document.createElement('style');
    style.id = 'account-settings-styles';
    style.textContent = `
        .setting-input {
            width: 100%;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 14px;
            transition: all 0.2s;
        }

        .setting-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
        }

        .setting-input:read-only {
            background: var(--bg-secondary);
            cursor: not-allowed;
            opacity: 0.7;
        }

        .setting-button {
            padding: 10px 20px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        .setting-button:hover {
            background: var(--bg-secondary);
            border-color: var(--primary);
        }

        .setting-danger-zone {
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid rgba(239, 68, 68, 0.3);
        }

        .setting-danger-zone label {
            color: #ef4444;
            font-weight: 600;
        }

        .setting-button-danger {
            background: rgba(239, 68, 68, 0.1);
            border-color: rgba(239, 68, 68, 0.3);
            color: #ef4444;
            margin-right: 8px;
            margin-top: 8px;
        }

        .setting-button-danger:hover {
            background: rgba(239, 68, 68, 0.2);
            border-color: #ef4444;
        }
    `;
    document.head.appendChild(style);
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize panel manager
    window.panelManager = new PanelManager();

    // Initialize floating buttons
    initializeFloatingButtons();

    // Add account settings
    setTimeout(() => {
        addAccountSettingsToPanel();
    }, 500);

    // ESC key handler to close panels
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && window.panelManager && window.panelManager.activePanel) {
            window.panelManager.close(window.panelManager.activePanel);
        }
    });
});

// Export for global access
window.PanelManager = PanelManager;
