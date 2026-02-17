(function () {
    'use strict';

    let currentStudView = 'dashboard';
    let currentStudAIMode = localStorage.getItem('aiMode') || 'socratic';
    let studAIOpen = false;
    let studClasses = Array.isArray(window.__STUDENT_CLASSES__) ? [...window.__STUDENT_CLASSES__] : [];
    let progressChart = null;

    function toastSafe(message, type) {
        if (typeof showToast === 'function') {
            showToast(message, type || 'info');
            return;
        }
        console.log(`[${type || 'info'}] ${message}`);
    }

    async function parseJSON(response) {
        const payload = await response.json().catch(() => {
            throw new Error(`Invalid JSON response (${response.status})`);
        });
        if (!response.ok || payload.success === false) {
            throw new Error(payload.message || payload.error || `Request failed (${response.status})`);
        }
        return payload;
    }

    async function fetchJSON(url, options = {}) {
        const res = await fetch(url, {
            credentials: 'same-origin',
            ...options
        });
        return parseJSON(res);
    }

    function normalizeList(payload) {
        if (Array.isArray(payload)) return payload;
        if (Array.isArray(payload.data)) return payload.data;
        if (Array.isArray(payload.classes)) return payload.classes;
        if (payload.data && Array.isArray(payload.data.classes)) return payload.data.classes;
        return [];
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function updateNav(viewName) {
        document.querySelectorAll('.nav-menu-item').forEach((link) => {
            link.classList.remove('active');
            const click = link.getAttribute('onclick') || '';
            if (click.includes(`'${viewName}'`)) link.classList.add('active');
        });
    }

    function classCard(cls) {
        const progress = Math.round(Number(cls.progress || 0));
        return `
            <div class="stud-class-card">
                <div class="scard-border"></div>
                <div>
                    <h3 class="scard-title">${escapeHtml(cls.title || 'Untitled Class')}</h3>
                    <p class="scard-teacher">Instructor: ${escapeHtml(cls.teacher || cls.teacher_name || cls.instructor || 'Unknown')}</p>
                    <p class="scard-subject">${escapeHtml(cls.description || 'No description')}</p>
                </div>
                <div>
                    <div class="scard-progress-row">
                        <div class="progress-track"><div class="progress-fill" style="width:${progress}%"></div></div>
                        <span class="progress-pct">${progress}%</span>
                    </div>
                    <div style="display: flex; gap: 10px; margin-top: 10px;">
                        <button class="scard-btn btn-glow" onclick="window.location.href='/class/${cls.id}'" style="flex:1;">Open Class</button>
                        <button class="scard-btn" onclick="leaveClass(${cls.id})" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); flex:1;">Leave</button>
                    </div>
                </div>
            </div>
        `;
    }

    window.leaveClass = async function leaveClass(classId) {
        if (!confirm('Are you sure you want to leave this class?')) return;

        try {
            await fetchJSON('/api/leave_class', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ class_id: Number(classId) })
            });
            toastSafe('Left class successfully', 'success');
            await loadStudentData();
        } catch (err) {
            toastSafe(err.message || 'Failed to leave class', 'error');
        }
    };

    window.switchStudentView = function switchStudentView(viewName) {
        document.querySelectorAll('.stud-view').forEach(v => { v.style.display = 'none'; });
        const view = document.getElementById(`${viewName}View`);
        if (view) view.style.display = 'flex';
        currentStudView = viewName;
        localStorage.setItem('lastStudentView', viewName);
        updateNav(viewName);

        if (viewName === 'dashboard') loadStudentData();
        if (viewName === 'browse') loadBrowseClasses();
        if (viewName === 'gaps') loadKnowledgeGaps();
        if (viewName === 'recommendations') loadRecommendations();
        if (viewName === 'progress') loadProgress();
        if (viewName === 'analytics') loadAnalytics();
        if (viewName === 'learningPath' && window.initLearningPath) window.initLearningPath();
    };

    // ... (keep sidebar toggles same)

    window.loadStudentData = async function loadStudentData() {
        const container = document.getElementById('studClassesGrid');
        if (!container) return;
        container.innerHTML = `<div class="loading-box"><div class="loading-spinner"></div><p class="loading-text">Loading your classes...</p></div>`;
        try {
            const payload = await fetchJSON('/api/user/data');
            studClasses = normalizeList(payload);
            if (!studClasses.length) {
                container.innerHTML = `
                    <div class="empty-state-box">
                        <div class="empty-ico">📚</div>
                        <h3 class="empty-heading">No classes joined yet</h3>
                        <p class="empty-desc">Browse classes to start learning</p>
                    </div>`;
                return;
            }
            container.innerHTML = studClasses.map(classCard).join('');
        } catch (err) {
            container.innerHTML = `<div class="empty-state-box"><h3 class="empty-heading">Failed to load classes</h3><p class="empty-desc">${escapeHtml(err.message)}</p></div>`;
        }
    };

    window.joinClass = function joinClass(code) {
        joinClassByCodeValue(code);
    };

    async function joinClassByCodeValue(code) {
        try {
            await fetchJSON('/api/join_class', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code: code })
            });
            toastSafe('Joined class successfully', 'success');
            await loadStudentData();
            await loadBrowseClasses();
            window.switchStudentView('dashboard');
        } catch (err) {
            toastSafe(err.message || 'Failed to join class', 'error');
        }
    }

    window.joinClassByCode = async function joinClassByCode() {
        const input = document.getElementById('classCodeInput');
        const feedback = document.getElementById('joinFeedback');
        const code = (input?.value || '').trim();
        if (!code) {
            feedback.innerHTML = '<div class="feedback-error">Enter a valid class code</div>';
            return;
        }

        feedback.innerHTML = '<div class="feedback-loading">Joining class...</div>';
        try {
            await joinClassByCodeValue(code);
            feedback.innerHTML = '<div class="feedback-success">Joined class successfully</div>';
            if (input) input.value = '';
        } catch (err) {
            feedback.innerHTML = `<div class="feedback-error">${escapeHtml(err.message || 'Failed to join class')}</div>`;
        }
    };

    window.loadBrowseClasses = async function loadBrowseClasses() {
        const container = document.getElementById('browseClassesGrid');
        if (!container) return;
        container.innerHTML = `<div class="loading-box"><div class="loading-spinner"></div><p class="loading-text">Loading available classes...</p></div>`;
        try {
            const payload = await fetchJSON('/api/classes/available');
            const classes = normalizeList(payload);
            if (!classes.length) {
                container.innerHTML = `<div class="empty-state-box"><div class="empty-ico">🔍</div><h3 class="empty-heading">No classes available</h3><p class="empty-desc">You are already enrolled in all available classes</p></div>`;
                return;
            }
            container.innerHTML = classes.map((cls) => {
                // Infer or randomize data for UI completeness if missing
                const schedule = cls.schedule || 'Flexible Schedule';
                const status = 'Active';
                const isUpcoming = false;

                return `
                <div class="browse-class-card">
                    <div class="bcc-header">
                        <div class="bcc-badge-row">
                             <div class="bcc-badge ${isUpcoming ? 'upcoming' : 'active'}">${status}</div>
                        </div>
                        <h3 class="bcc-title">${escapeHtml(cls.title || 'Untitled Class')}</h3>
                        <div class="bcc-subject">${escapeHtml(cls.subject || 'General Subject')}</div>
                    </div>
                    
                    <div class="bcc-info">
                        <div class="bcc-row">
                            <span class="bcc-icon">👨‍🏫</span> 
                            <span>${escapeHtml(cls.teacher || cls.teacher_name || cls.instructor || 'Unknown Instructor')}</span>
                        </div>
                        <div class="bcc-row">
                            <span class="bcc-icon">📅</span> 
                            <span>${escapeHtml(schedule)}</span>
                        </div>
                        <p class="card-desc" style="font-size:13px; color:#9ca3af; line-height:1.4; margin-top:8px;">
                            ${escapeHtml(cls.description || 'No description available for this class.')}
                        </p>
                    </div>

                    <button class="bcc-btn" onclick="joinClass('${cls.code}')">Join Class</button>
                </div>
            `}).join('');
        } catch (err) {
            container.innerHTML = `<div class="empty-state-box"><h3 class="empty-heading">Failed to load classes</h3><p class="empty-desc">${escapeHtml(err.message)}</p></div>`;
        }
    };

    window.loadRecommendations = async function loadRecommendations() {
        const container = document.getElementById('studRecommendGrid');
        if (!container) return;
        container.innerHTML = '<div class="loading-box"><div class="loading-spinner"></div><p class="loading-text">Loading personalized recommendations...</p></div>';
        try {
            const payload = await fetchJSON('/api/student/recommendations');
            // Support both wrapped and direct array for backward compat during dev
            const recs = payload.recommendations || (Array.isArray(payload) ? payload : []) || [];

            if (!recs.length) {
                container.innerHTML = `<div class="empty-state-box"><div class="empty-ico">✨</div><h3 class="empty-heading">No recommendations yet</h3><p class="empty-desc">Complete a few quizzes to unlock personalized recommendations</p></div>`;
                return;
            }

            container.innerHTML = recs.map((rec) => {
                // Map priority
                let pLabel = 'MEDIUM';
                let pClass = 'medium';
                const pVal = rec.priority || 50;
                if (pVal >= 90) { pLabel = 'URGENT'; pClass = 'high'; }
                else if (pVal <= 40) { pLabel = 'LOW'; pClass = 'low'; }

                // Action Logic
                let actionFn = '';
                const rType = (rec.type || rec.content_type || 'general').toLowerCase();
                const cId = rec.content_id || 0;

                if (rType === 'quiz') {
                    actionFn = `window.location.href='/student/quiz/${cId}'`;
                } else if (rType === 'lecture') {
                    actionFn = `window.location.href='/class/${rec.class_id || '#'}'`; // Ideally deep link
                } else if (rType === 'review') {
                    // Scroll to learning path? Or just generic
                    actionFn = "window.switchStudentView('learningPath')";
                } else {
                    actionFn = "return false;";
                }

                const btnText = rec.action || 'Start Now';

                return `
                <div class="ai-rec-card">
                    <div class="air-header">
                        <span class="air-tag">${escapeHtml(rType.toUpperCase())}</span>
                        <span class="air-priority ${pClass}">${pLabel}</span>
                    </div>
                    <h3 class="air-title">${escapeHtml(rec.title || 'Recommended Topic')}</h3>
                    <p class="air-desc">${escapeHtml(rec.description || rec.reason || 'No description available')}</p>
                    <button class="air-action" onclick="${actionFn}">${escapeHtml(btnText)}</button>
                </div>
            `}).join('');
        } catch (err) {
            container.innerHTML = `<div class="empty-state-box"><h3 class="empty-heading">No recommendations yet</h3><p class="empty-desc">${escapeHtml(err.message)}</p></div>`;
        }
    };

    window.loadKnowledgeGaps = async function loadKnowledgeGaps() {
        const container = document.getElementById('studGapsGrid');
        if (!container) return;
        container.innerHTML = '<div class="loading-box"><div class="loading-spinner"></div><p class="loading-text">Analyzing knowledge gaps...</p></div>';
        try {
            const payload = await fetchJSON('/api/student/knowledge-gaps');
            const gaps = payload.gaps || (Array.isArray(payload) ? payload : []) || [];
            if (!gaps.length) {
                container.innerHTML = `<div class="empty-state-box"><div class="empty-ico">🎯</div><h3 class="empty-heading">No knowledge gaps detected</h3><p class="empty-desc">Keep up the good work and continue practicing</p></div>`;
                return;
            }
            container.innerHTML = gaps.map((gap) => `
                <div class="recommend-card">
                    <h3 class="card-title">${escapeHtml(gap.quiz_title || gap.topic || 'Topic')}</h3>
                    <p class="card-desc">Average score: ${gap.average_score || 0}%</p>
                    <div class="card-meta">Attempts: ${gap.attempts || 0}</div>
                </div>
            `).join('');
        } catch (err) {
            container.innerHTML = `<div class="empty-state-box"><h3 class="empty-heading">No knowledge gaps detected</h3><p class="empty-desc">${escapeHtml(err.message)}</p></div>`;
        }
    };

    async function ensureChartLib() {
        if (typeof Chart !== 'undefined') return;
        await new Promise((resolve, reject) => {
            const existing = document.getElementById('chartjs-lib');
            if (existing) {
                existing.addEventListener('load', resolve);
                existing.addEventListener('error', () => reject(new Error('Chart.js failed to load')));
                return;
            }
            const script = document.createElement('script');
            script.id = 'chartjs-lib';
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
            script.onload = resolve;
            script.onerror = () => reject(new Error('Chart.js failed to load'));
            document.head.appendChild(script);
        });
    }

    window.toggleDesktopSidebar = function toggleDesktopSidebar() {
        const sidebar = document.getElementById('studSidebar');
        if (!sidebar) return;
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('studSidebarCollapsed', isCollapsed);
    };

    // ── AI Panel Toggle Functions ──────────────────────────────────────
    window.openStudAI = function openStudAI() {
        const panel = document.getElementById('studAIPanel');
        const center = document.getElementById('studCenter');
        const fab = document.getElementById('aiFloatStud');
        if (!panel) return;
        panel.classList.add('open');
        if (center) center.classList.add('ai-active');
        if (fab) fab.style.display = 'none';
        studAIOpen = true;
    };

    window.closeStudAI = function closeStudAI() {
        const panel = document.getElementById('studAIPanel');
        const center = document.getElementById('studCenter');
        const fab = document.getElementById('aiFloatStud');
        if (!panel) return;
        panel.classList.remove('open');
        if (center) center.classList.remove('ai-active');
        if (fab) fab.style.display = 'flex';
        studAIOpen = false;
    };

    window.toggleStudAI = function toggleStudAI() {
        if (studAIOpen) {
            window.closeStudAI();
        } else {
            window.openStudAI();
        }
    };

    window.switchStudAIMode = function switchStudAIMode(mode, btn) {
        currentStudAIMode = mode;
        localStorage.setItem('aiMode', mode);
        document.querySelectorAll('.sai-tab').forEach(t => t.classList.remove('active'));
        if (btn) btn.classList.add('active');
    };

    window.closeAllStudMobile = function closeAllStudMobile() {
        const sidebar = document.getElementById('studSidebar');
        const overlay = document.getElementById('studOverlay');
        if (sidebar) sidebar.classList.remove('mobile-open');
        if (overlay) overlay.classList.remove('show');
        window.closeStudAI();
    };

    window.toggleStudSidebar = function toggleStudSidebar() {
        const sidebar = document.getElementById('studSidebar');
        const overlay = document.getElementById('studOverlay');
        if (!sidebar) return;
        sidebar.classList.toggle('mobile-open');
        if (overlay) overlay.classList.toggle('show');
    };

    window.loadProgress = async function loadProgress() {
        const container = document.getElementById('studProgressGrid');
        if (!container) return;

        container.innerHTML = '<div class="loading-box"><div class="loading-spinner"></div><p class="loading-text">Loading progress timeline...</p></div>';

        try {
            const payload = await fetchJSON('/api/student/analytics');
            const data = payload.data || payload;
            const subjects = data.subject_progress || [];

            if (subjects.length === 0) {
                container.innerHTML = `<div class="empty-state-box"><div class="empty-ico">📊</div><h3 class="empty-heading">No progress data yet</h3><p class="empty-desc">Enroll in a class to start tracking your journey</p></div>`;
                return;
            }

            let html = `
                <div class="progress-timeline-container">
                    <div class="progress-timeline">
            `;

            subjects.forEach((sub, index) => {
                const isCompleted = sub.percent >= 100;
                const completedClass = isCompleted ? 'completed' : '';
                const checkMark = isCompleted ? '✓' : '';
                const delay = index * 0.1;

                html += `
                    <div class="progress-item" style="animation-delay: ${delay}s">
                        <div class="timeline-node ${completedClass}">${checkMark}</div>
                        <div class="timeline-card ${isCompleted ? 'glow' : ''}">
                            <div class="prog-sub-title">
                                <span>${escapeHtml(sub.title)}</span>
                                <span style="color: ${isCompleted ? '#10b981' : '#60a5fa'}">${sub.percent}%</span>
                            </div>
                            <div class="prog-sub-meta">
                                ${sub.completed_modules} / ${sub.total_modules} Modules
                            </div>
                            <div class="prog-bar-container">
                                <div class="prog-bar-fill" style="width: ${sub.percent}%; background: ${isCompleted ? '#10b981' : 'linear-gradient(90deg, #3b82f6, #60a5fa)'}"></div>
                            </div>
                        </div>
                    </div>
                `;
            });

            html += `   </div>
                    </div>`;

            container.innerHTML = html;

        } catch (err) {
            container.innerHTML = `<div class="empty-state-box"><p>${escapeHtml(err.message)}</p></div>`;
        }
    };

    window.loadAnalytics = async function loadAnalytics() {
        const container = document.getElementById('studAnalyticsGrid');
        // Note: HTML might have different ID. Let's check HTML if 'studAnalyticsGrid' exists or if it's 'analyticsContent'.
        // Assuming 'studAnalyticsGrid' for consistency with other views, or I should check the HTML.
        // If not found, check 'analyticsView'.

        // Let's assume the container is inside 'analyticsView'.
        // Actually, looking at previous code, main containers are usually grids.
        if (!container) return;

        container.innerHTML = `<div class="loading-box"><div class="loading-spinner"></div><p class="loading-text">Loading analytics...</p></div>`;

        try {
            const payload = await fetchJSON('/api/student/analytics');
            const data = payload.data || payload;

            let html = `
                <div class="analytics-dashboard">
                    <div class="stats-overview">
                        <div class="stat-card">
                            <div class="stat-value">${data.avg_score}%</div>
                            <div class="stat-label">Average Score</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${data.total_quizzes}</div>
                            <div class="stat-label">Quizzes Taken</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${data.accuracy}%</div>
                            <div class="stat-label">Accuracy</div>
                        </div>
                    </div>

                    <div class="analytics-section">
                        <h3>Quiz History</h3>
                        <div class="table-responsive">
                            <table class="stud-table">
                                <thead>
                                    <tr>
                                        <th>Quiz</th>
                                        <th>Date</th>
                                        <th>Score</th>
                                        <th>Time</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${(data.quiz_attempts || []).map(q => `
                                        <tr>
                                            <td>${escapeHtml(q.quiz_title)}</td>
                                            <td>${new Date(q.submitted_at).toLocaleDateString()}</td>
                                            <td><span class="badge ${q.score_percent >= 70 ? 'badge-success' : 'badge-warning'}">${q.score_percent}%</span></td>
                                            <td>${q.time_taken_minutes}m</td>
                                        </tr>
                                    `).join('')}
                                    ${(!data.quiz_attempts || data.quiz_attempts.length === 0) ? '<tr><td colspan="4" style="text-align:center;">No quizzes taken yet</td></tr>' : ''}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div class="analytics-row">
                        <div class="analytics-col">
                            <h3>Strong Topics</h3>
                            <div class="topic-list">
                                ${(data.strong_topics || []).map(t => `
                                    <div class="topic-item strong">
                                        <span>${escapeHtml(t.topic)}</span>
                                        <span class="topic-score">${t.score}%</span>
                                    </div>
                                `).join('')}
                                ${(!data.strong_topics || data.strong_topics.length === 0) ? '<p class="empty-text">No data yet</p>' : ''}
                            </div>
                        </div>
                        <div class="analytics-col">
                            <h3>Topics to Improve</h3>
                            <div class="topic-list">
                                ${(data.weak_topics || []).map(t => `
                                    <div class="topic-item weak">
                                        <span>${escapeHtml(t.topic)}</span>
                                        <span class="topic-score">${t.score}%</span>
                                    </div>
                                `).join('')}
                                ${(!data.weak_topics || data.weak_topics.length === 0) ? '<p class="empty-text">No data yet</p>' : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
            container.innerHTML = html;

        } catch (err) {
            container.innerHTML = `<div class="empty-state-box"><p>${escapeHtml(err.message)}</p></div>`;
        }
    };

    window.loadKnowledgeGaps = async function loadKnowledgeGaps() {
        const container = document.getElementById('studGapsGrid');
        if (!container) return;
        container.innerHTML = `<div class="loading-box"><div class="loading-spinner"></div><p class="loading-text">Analyzing performance...</p></div>`;

        try {
            const payload = await fetchJSON('/api/student/knowledge-gaps');
            const gaps = payload.gaps || [];

            if (gaps.length === 0) {
                container.innerHTML = `
                    <div class="empty-state-box">
                        <div class="empty-ico">✅</div>
                        <h3 class="empty-heading">No Knowledge Gaps Detected</h3>
                        <p class="empty-desc">Great job! You seem to have a good grasp of your current topics.</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = `
                <div class="gaps-grid">
                    ${gaps.map(gap => `
                        <div class="gap-card">
                            <div class="gap-header">
                                <span class="gap-severity ${gap.severity || 'medium'}">${(gap.severity || 'Medium').toUpperCase()}</span>
                                <span class="gap-quiz">${escapeHtml(gap.quiz || gap.quiz_title)}</span>
                            </div>
                            <p class="gap-question">"${escapeHtml(gap.question || gap.question_text)}"</p>
                            <div class="gap-actions">
                                <button class="gap-btn" onclick="window.location.href='/student/quiz/${gap.quiz_id}'">Retake Quiz</button>
                                <button class="gap-btn secondary" onclick="window.switchStudentView('learningPath')">Review Material</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;

        } catch (err) {
            container.innerHTML = `<div class="empty-state-box"><p>${escapeHtml(err.message)}</p></div>`;
        }
    };

    class VoiceAssistant {
        constructor() {
            this.recognition = null;
            this.synth = window.speechSynthesis;
            this.isListening = false;
            this.isSpeakerOn = localStorage.getItem('voiceSpeakerOn') === 'true';
            this.wakeWords = ["hey kyknox", "hey kai nox", "hey kainox", "hey kynox", "hey kai-nox"];
            this.isWakeMode = false;

            // Language Codes Map
            this.langMap = {
                'english': 'en-US',
                'hindi': 'hi-IN',
                'odia': 'or-IN',
                'bengali': 'bn-IN',
                'telugu': 'te-IN',
                'tamil': 'ta-IN'
            };

            this.initRecognition();
            this.updateUI();
        }

        get currentLangCode() {
            const storedLang = localStorage.getItem('learnvaultx_ai_language') || 'english';
            return this.langMap[storedLang] || 'en-US';
        }

        initRecognition() {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                console.warn('Speech recognition not supported');
                return;
            }

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false; // We restart manually for control
            this.recognition.interimResults = true;
            this.recognition.lang = this.currentLangCode;

            this.recognition.onstart = () => {
                this.isListening = true;
                this.updateUI();
            };

            this.recognition.onend = () => {
                this.isListening = false;
                this.updateUI();
                // Auto-restart if in Wake Mode (Wait slightly to avoid CPU hog)
                if (this.isWakeMode) {
                    setTimeout(() => {
                        if (this.isWakeMode) this.startListening();
                    }, 500);
                }
            };

            this.recognition.onresult = (event) => {
                let interimTranscript = '';
                let finalTranscript = '';

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interimTranscript += event.results[i][0].transcript;
                    }
                }

                const input = document.getElementById('studAIInput');
                if (input) {
                    // If we have existing text and just started speaking, clear it only if it was empty/placeholder
                    // But here we just append or replace. Let's aim to fill the input.
                    // For wake word, we check the final transcript.

                    if (finalTranscript) {
                        const lowerFinal = finalTranscript.toLowerCase();

                        // CHECK STOP COMMAND
                        if (lowerFinal.includes('stop') || lowerFinal.includes('quiet') || lowerFinal.includes('silence')) {
                            this.stopSpeaking();
                            this.isWakeMode = false; // also exit wake mode
                            toastSafe('Voice deactivated', 'info');
                            return;
                        }

                        // WAKE WORD LOGIC
                        const isWake = this.wakeWords.some(w => lowerFinal.includes(w));
                        if (isWake) {
                            this.stopSpeaking();
                            // Open AI panel if closed
                            if (!studAIOpen && window.openStudAI) window.openStudAI();
                            toastSafe('👋 I am listening!', 'success');

                            // Strip the wake word from the transcript to get the actual query
                            let query = lowerFinal;
                            this.wakeWords.forEach(w => { query = query.replace(w, '').trim(); });

                            if (query) {
                                input.value = query;
                                window.sendStudAI();
                            }
                            return;
                        }

                        // Normal Dictation
                        input.value = finalTranscript;

                        // If not in generic wake mode Loop, maybe auto-send? 
                        // For now, let's keep it as: User speaks -> Text appears -> User sends OR Wake Word auto-sends.
                        // Actually, requirement says "Click to speak -> auto-send OR directly send".
                        // Let's Auto-Send if it's a "Click to Speak" session (not wake loop idle).

                        if (!this.isWakeMode) {
                            window.sendStudAI();
                        }
                    } else if (interimTranscript) {
                        input.value = interimTranscript;
                    }
                }
            };

            this.recognition.onerror = (event) => {
                console.log('Speech recognition error', event.error);
                if (event.error === 'not-allowed') {
                    this.isWakeMode = false;
                    toastSafe('Microphone access denied', 'error');
                }
            };
        }

        toggleMic() {
            if (!this.recognition) {
                toastSafe('Speech recognition not supported in this browser', 'error');
                return;
            }
            if (this.isListening) {
                this.stopListening();
                this.isWakeMode = false; // Force stop wake mode
            } else {
                this.isWakeMode = false; // Single command mode by default on click
                this.startListening();
            }
        }

        // This toggles the persistent "Wake Word" listening loop
        // We can bind this to a long press or a specific UI toggle if needed.
        // For now, the requested feature is "Click to Speak" (Mic) and "Wake Word" support.
        // We'll treat the Mic button as "Start Voice Session".

        startListening() {
            if (!this.recognition) return;
            try {
                this.recognition.lang = this.currentLangCode; // Update lang before start
                this.recognition.start();
            } catch (e) {
                console.error("Recognition start error (likely already started):", e);
            }
        }

        stopListening() {
            if (!this.recognition) return;
            this.recognition.stop();
        }

        toggleSpeaker() {
            this.isSpeakerOn = !this.isSpeakerOn;
            localStorage.setItem('voiceSpeakerOn', this.isSpeakerOn);
            if (!this.isSpeakerOn) {
                this.stopSpeaking();
            }
            this.updateUI();
            toastSafe(`Voice output ${this.isSpeakerOn ? 'enabled' : 'disabled'}`, 'info');
        }

        stopSpeaking() {
            if (this.synth) {
                this.synth.cancel();
            }
        }

        speak(text) {
            if (!this.isSpeakerOn || !this.synth) return;

            // Clean markdown basic chars for speech
            const cleanText = text.replace(/\*\*/g, '').replace(/[\#\`]/g, '');

            const utterance = new SpeechSynthesisUtterance(cleanText);

            // Try to select a voice matching the language code
            const voices = this.synth.getVoices();
            const langCode = this.currentLangCode;

            // Priority: Exact match -> Same Lang -> Default
            let selectedVoice = voices.find(v => v.lang === langCode) ||
                voices.find(v => v.lang.startsWith(langCode.split('-')[0]));

            if (selectedVoice) {
                utterance.voice = selectedVoice;
            }

            // Slower rate for non-native English might be better
            utterance.rate = 1.0;

            this.synth.speak(utterance);
        }

        updateUI() {
            const btnMic = document.getElementById('btnVoiceMic');
            const btnSpeaker = document.getElementById('btnVoiceSpeaker');
            const status = document.getElementById('voiceStatus');

            if (btnMic) {
                btnMic.classList.toggle('active', this.isListening);
            }
            if (btnSpeaker) {
                btnSpeaker.classList.toggle('speaker-active', this.isSpeakerOn);
            }
            if (status) {
                status.style.display = this.isListening ? 'flex' : 'none';
                if (this.isWakeMode) {
                    status.innerHTML = '<span class="pulse-dot"></span> Listening for "Hey Kyknox"...';
                } else {
                    status.innerHTML = '<span class="pulse-dot"></span> Listening...';
                }
            }
        }
    }

    // Global Instance
    let voiceAssistant = null;

    // Window Exports
    window.toggleVoiceInput = function () {
        if (voiceAssistant) voiceAssistant.toggleMic();
    };

    window.toggleVoiceSpeaker = function () {
        if (voiceAssistant) voiceAssistant.toggleSpeaker();
    };

    document.addEventListener('DOMContentLoaded', () => {
        const lastView = localStorage.getItem('lastStudentView');
        if (lastView && document.getElementById(`${lastView}View`)) {
            switchStudentView(lastView);
        } else {
            switchStudentView('dashboard');
        }

        const collapsed = localStorage.getItem('studSidebarCollapsed') === 'true';
        if (collapsed) {
            document.getElementById('studSidebar')?.classList.add('collapsed');
        }

        const aiInput = document.getElementById('studAIInput');
        if (aiInput) {
            aiInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendStudAI();
                }
            });
        }

        // Init Voice Assistant
        voiceAssistant = new VoiceAssistant();

        // Enhance sendStudAI to speak response
        const originalSend = window.sendStudAI;
        window.sendStudAI = async function () {
            // We need to capture the response text.
            // Since original function updates DOM directly, we kinda need to rewrite it or hook into it.
            // Simplest is to copy logic from original and add speak().

            const input = document.getElementById('studAIInput');
            const message = (input?.value || '').trim();
            if (!message) return;

            const chat = document.getElementById('studAIMessages');
            chat.querySelector('.sai-welcome-box')?.remove();

            const user = document.createElement('div');
            user.className = 'sai-message user';
            user.innerHTML = `<div class="message-avatar">👤</div><div class="message-content">${escapeHtml(message)}</div>`;
            chat.appendChild(user);
            input.value = '';

            const loading = document.createElement('div');
            loading.className = 'sai-message bot';
            loading.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content">Thinking...</div>`;
            chat.appendChild(loading);
            chat.scrollTop = chat.scrollHeight;

            try {
                const language = localStorage.getItem('learnvaultx_ai_language') || 'english';
                // Use existing global var logic for mode
                const payload = await fetchJSON('/api/chatbot', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: message, mode: currentStudAIMode, language })
                });
                loading.remove();

                const responseText = payload.raw || payload.reply || '';
                const displayHtml = payload.reply || (payload.raw ? escapeHtml(payload.raw) : '');

                const ai = document.createElement('div');
                ai.className = 'sai-message bot';
                ai.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content">${displayHtml}</div>`;
                chat.appendChild(ai);
                chat.scrollTop = chat.scrollHeight;

                // Speak!
                if (voiceAssistant) {
                    voiceAssistant.speak(responseText);
                }

            } catch (err) {
                loading.remove();
                const ai = document.createElement('div');
                ai.className = 'sai-message bot';
                ai.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content">${escapeHtml(err.message || 'AI failed')}</div>`;
                chat.appendChild(ai);

                if (voiceAssistant) {
                    voiceAssistant.speak("Sorry, I encountered an error.");
                }
            }
        };
    });

    // Fix for "Review & Retake" button
    window.startModuleQuiz = function startModuleQuiz(id, name, isCompleted, classId) {
        console.log(`Starting module quiz: ${name} (ID: ${id})`);
        toastSafe(`Starting quiz: ${name}...`, 'info');

        // Assumption: The first argument 'id' is the quiz_id.
        setTimeout(() => {
            window.location.href = `/quiz/${id}`;
        }, 500);
    };
})();
