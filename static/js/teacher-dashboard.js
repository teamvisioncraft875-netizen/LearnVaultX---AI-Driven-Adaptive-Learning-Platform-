(function () {
    'use strict';

    let currentView = 'dashboard';
    let currentAIMode = localStorage.getItem('aiMode') || 'expert';
    let aiOpen = false;
    let questionCount = 0;
    let analyticsChart = null;

    const initialClasses = Array.isArray(window.__TEACHER_CLASSES__) ? window.__TEACHER_CLASSES__ : [];
    let classesCache = [...initialClasses];

    function jsonOrThrow(response) {
        return response.json().catch(() => {
            throw new Error(`Invalid JSON response (${response.status})`);
        });
    }

    async function fetchJSON(url, options = {}) {
        const response = await fetch(url, {
            credentials: 'same-origin',
            ...options
        });
        const payload = await jsonOrThrow(response);
        if (!response.ok || payload.success === false) {
            throw new Error(payload.message || payload.error || `Request failed: ${response.status}`);
        }
        return payload;
    }

    function toastSafe(message, type) {
        if (typeof showToast === 'function') {
            showToast(message, type || 'info');
            return;
        }
        console.log(`[${type || 'info'}] ${message}`);
    }

    function updateNav(viewName) {
        document.querySelectorAll('.nav-menu-item').forEach((link) => {
            link.classList.remove('active');
            const click = link.getAttribute('onclick') || '';
            if (click.includes(`'${viewName}'`)) {
                link.classList.add('active');
            }
        });
    }

    function updateClassOptions() {
        const select = document.getElementById('analyticsClassSelect');
        if (!select) return;

        const previous = select.value;
        select.innerHTML = '<option value="">Select a class...</option>';
        classesCache.forEach((c) => {
            const option = document.createElement('option');
            option.value = c.id;
            option.textContent = c.title;
            select.appendChild(option);
        });
        if (previous && classesCache.some(c => String(c.id) === String(previous))) {
            select.value = previous;
        }
    }

    function renderClassCard(c) {
        return `
            <div class="class-card">
                <div class="card-border-glow"></div>
                <h3 class="card-title">${escapeHtml(c.title || 'Untitled Class')}</h3>
                <p class="card-desc">${escapeHtml(c.description || 'No description')}</p>
                
                <div class="class-code-section" style="margin: 10px 0; background: rgba(255,255,255,0.1); padding: 5px 10px; border-radius: 6px; display: flex; align-items: center; justify-content: space-between; cursor: pointer;" onclick="navigator.clipboard.writeText('${c.code}'); toastSafe('Code copied: ${c.code}', 'success')">
                    <span style="font-weight: bold; color: #a855f7;">Code: ${c.code || 'N/A'}</span>
                    <span style="font-size: 0.8em; opacity: 0.7;">📋 Copy</span>
                </div>

                <div class="card-meta">
                    <span class="meta-item">👥 ${c.student_count || 0} students</span>
                    <span class="meta-item">📚 ${c.lecture_count || 0} lectures</span>
                </div>
                <div class="card-actions">
                    <button class="btn-card primary" onclick="window.location.href='/class/${c.id}'">View Class</button>
                    <button class="btn-card secondary" onclick="showUploadLectureModal(${c.id}, '${escapeHtml((c.title || '').replace(/'/g, "\\'"))}')">Upload</button>
                    <button class="btn-card secondary" onclick="showCreateQuizModal(${c.id}, '${escapeHtml((c.title || '').replace(/'/g, "\\'"))}')">Quiz</button>
                </div>
            </div>
        `;
    }

    function refreshClassGrid() {
        const container = document.getElementById('classListContainer');
        if (!container) return;
        if (!classesCache.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">◈</div>
                    <h3 class="empty-title">No classes yet</h3>
                    <p class="empty-text">Create your first class to start teaching</p>
                    <button class="btn-primary" onclick="showCreateClassModal()">Create Class</button>
                </div>
            `;
            return;
        }
        container.innerHTML = classesCache.map(renderClassCard).join('');
    }

    function updateStats() {
        const totalStudents = classesCache.reduce((sum, c) => sum + (c.student_count || 0), 0);
        const totalLectures = classesCache.reduce((sum, c) => sum + (c.lecture_count || 0), 0);
        const totalClasses = classesCache.length;

        const classesEl = document.getElementById('totalClasses');
        const studentsEl = document.getElementById('totalStudents');
        const lecturesEl = document.getElementById('totalLectures');

        if (classesEl) classesEl.textContent = totalClasses;
        if (studentsEl) studentsEl.textContent = totalStudents;
        if (lecturesEl) lecturesEl.textContent = totalLectures;
    }

    async function loadTeacherClasses() {
        try {
            const payload = await fetchJSON('/api/teacher/classes');
            classesCache = Array.isArray(payload.data) ? payload.data : (Array.isArray(payload) ? payload : []);
            updateClassOptions();
            refreshClassGrid();
            updateStats();
        } catch (err) {
            console.error('Failed to load teacher classes', err);
        }
    }

    function ensureChartLib() {
        return new Promise((resolve, reject) => {
            if (typeof Chart !== 'undefined') return resolve();
            const existing = document.getElementById('chartjs-lib');
            if (existing) {
                existing.addEventListener('load', () => resolve());
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

    function emptyState(message) {
        return `<div class="empty-state"><p class="empty-text">${escapeHtml(message)}</p></div>`;
    }

    async function loadClassAnalytics(classId) {
        const dataContainer = document.getElementById('analyticsData');
        const chartContainer = document.getElementById('analyticsChartContainer');
        if (!dataContainer || !chartContainer) return;

        if (!classId) {
            dataContainer.innerHTML = emptyState('Select a class to see analytics');
            chartContainer.style.display = 'none';
            return;
        }

        try {
            await ensureChartLib();
            const payload = await fetchJSON(`/api/analytics?class_id=${encodeURIComponent(classId)}`);
            const metrics = Array.isArray(payload.data) ? payload.data : (Array.isArray(payload) ? payload : []);

            if (!metrics.length) {
                dataContainer.innerHTML = emptyState('No Data Available Yet');
                chartContainer.style.display = 'none';
                if (analyticsChart) analyticsChart.destroy();
                analyticsChart = null;
                return;
            }

            chartContainer.style.display = 'block';
            const ctx = document.getElementById('classAnalyticsChart').getContext('2d');
            if (analyticsChart) analyticsChart.destroy();

            analyticsChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: metrics.map(m => m.student_name || `Student ${m.user_id}`),
                    datasets: [{
                        label: 'Average Score (%)',
                        data: metrics.map(m => Number(m.score_avg || m.quiz_score || 0)),
                        backgroundColor: function (context) {
                            const chart = context.chart;
                            const { ctx, chartArea } = chart;
                            if (!chartArea) return null;
                            const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
                            gradient.addColorStop(0, '#3b82f6');
                            gradient.addColorStop(1, '#a855f7');
                            return gradient;
                        },
                        borderRadius: 8,
                        barThickness: 30,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.9)',
                            titleColor: '#e2e8f0',
                            bodyColor: '#cbd5e1',
                            borderColor: 'rgba(168, 85, 247, 0.3)',
                            borderWidth: 1,
                            padding: 12,
                            displayColors: false,
                            callbacks: {
                                label: function (context) {
                                    return `Avg Score: ${context.parsed.y}%`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#94a3b8', callback: v => v + '%' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#94a3b8' }
                        }
                    }
                }
            });

            dataContainer.innerHTML = metrics.map((metric) => `
                <div class="analytics-card">
                    <h4 class="analytics-name">${escapeHtml(metric.student_name || 'Student')}</h4>
                    <div class="analytics-stats">
                        <div class="analytics-stat"><span class="stat-label">Avg Score:</span><span class="stat-value">${Number(metric.score_avg || metric.quiz_score || 0).toFixed(1)}%</span></div>
                        <div class="analytics-stat"><span class="stat-label">Rating:</span><span class="stat-value">${Number(metric.rating || 0).toFixed(1)}</span></div>
                    </div>
                </div>
            `).join('');
        } catch (err) {
            console.error('Failed loading analytics', err);
            dataContainer.innerHTML = emptyState('No Data Available Yet');
            chartContainer.style.display = 'none';
            toastSafe(err.message || 'Failed to load analytics', 'error');
        }
    }

    async function loadStudents() {
        const container = document.getElementById('studentsListContainer');
        if (!container) return;
        container.innerHTML = '<div class="empty-state"><p class="empty-text">Loading students...</p></div>';
        try {
            const payload = await fetchJSON('/api/teacher/students');
            const students = Array.isArray(payload.data) ? payload.data : (Array.isArray(payload) ? payload : []);
            if (!students.length) {
                container.innerHTML = emptyState('No students enrolled yet');
                return;
            }
            container.innerHTML = students.map((student) => `
                <div class="student-card">
                    <div class="student-avatar">${escapeHtml((student.name || 'S')[0])}</div>
                    <h4 class="student-name">${escapeHtml(student.name || 'Student')}</h4>
                    <p class="student-email">${escapeHtml(student.email || '')}</p>
                    <p class="student-meta">Quizzes taken: ${student.quizzes_taken || 0}</p>
                </div>
            `).join('');
        } catch (err) {
            console.error('Failed loading students', err);
            container.innerHTML = emptyState('Failed to load students');
        }
    }

    async function loadAlerts() {
        const container = document.getElementById('alertsListContainer');
        if (!container) return;
        container.innerHTML = '<div class="empty-state"><p class="empty-text">Loading alerts...</p></div>';
        try {
            const payload = await fetchJSON('/api/teacher/alerts');
            const alerts = payload.alerts || (payload.data && payload.data.alerts) || [];
            if (!alerts.length) {
                container.innerHTML = emptyState('No active alerts');
                return;
            }
            container.innerHTML = alerts.map((alert) => `
                <div class="analytics-card">
                    <h4 class="analytics-name">${escapeHtml(alert.student_name || 'Student')} • ${escapeHtml(alert.class_title || 'Class')}</h4>
                    <p class="analytics-stat"><span class="stat-label">${escapeHtml(alert.alert_type || 'alert')}</span></p>
                    <p class="analytics-stat"><span class="stat-value">${escapeHtml(alert.message || '')}</span></p>
                </div>
            `).join('');
        } catch (err) {
            console.error('Failed loading alerts', err);
            container.innerHTML = emptyState('Failed to load alerts');
        }
    }

    async function loadFeedback() {
        const container = document.getElementById('feedbackListContainer');
        if (!container) return;
        container.innerHTML = '<div class="empty-state"><p class="empty-text">Loading feedback...</p></div>';
        try {
            const payload = await fetchJSON('/api/teacher/feedback');
            const feedback = payload.feedback || (payload.data && payload.data.feedback) || [];
            if (!feedback.length) {
                container.innerHTML = emptyState('No feedback yet');
                return;
            }
            container.innerHTML = feedback.map((item) => `
                <div class="analytics-card">
                    <h4 class="analytics-name">${escapeHtml(item.student_name || 'Student')} • ${'★'.repeat(Number(item.rating || 0))}</h4>
                    <p class="analytics-stat"><span class="stat-value">${escapeHtml(item.message || 'No comment')}</span></p>
                    <p class="analytics-stat"><span class="stat-label">${escapeHtml(item.created_at || '')}</span></p>
                </div>
            `).join('');
        } catch (err) {
            console.error('Failed loading feedback', err);
            container.innerHTML = emptyState('Failed to load feedback');
        }
    }

    window.switchView = function switchView(viewName) {
        document.querySelectorAll('.dash-view').forEach(v => { v.style.display = 'none'; });
        const viewEl = document.getElementById(`${viewName}View`);
        if (viewEl) viewEl.style.display = 'flex';
        updateNav(viewName);
        currentView = viewName;
        localStorage.setItem('lastTeacherView', viewName);

        if (viewName === 'students') loadStudents();
        if (viewName === 'alerts') loadAlerts();
        if (viewName === 'feedback') loadFeedback();
    };

    window.toggleMobileSidebar = function toggleMobileSidebar() {
        const sidebar = document.getElementById('dashSidebar');
        const overlay = document.getElementById('dashOverlay');
        if (!sidebar || !overlay) return;
        sidebar.classList.toggle('mobile-show');
        overlay.classList.toggle('show');
    };

    window.toggleAI = function toggleAI() {
        if (aiOpen) window.closeAI();
        else window.openAI();
    };

    window.closeAllMobile = function closeAllMobile() {
        document.getElementById('dashSidebar')?.classList.remove('mobile-show');
        document.getElementById('dashOverlay')?.classList.remove('show');
    };

    window.openAI = function openAI() {
        document.getElementById('dashAIPanel')?.classList.add('open');
        document.getElementById('dashCenter')?.classList.add('ai-active');
        const float = document.getElementById('aiFloat');
        if (float) float.style.display = 'none';
        aiOpen = true;
    };

    window.closeAI = function closeAI() {
        document.getElementById('dashAIPanel')?.classList.remove('open');
        document.getElementById('dashCenter')?.classList.remove('ai-active');
        const float = document.getElementById('aiFloat');
        if (float) float.style.display = 'flex';
        aiOpen = false;
    };

    window.switchAIMode = function switchAIMode(mode, el) {
        currentAIMode = mode;
        localStorage.setItem('aiMode', mode);
        document.querySelectorAll('.mode-tab').forEach(tab => tab.classList.toggle('active', tab.dataset.mode === mode));
        if (el) el.classList.add('active');
    };

    window.sendAIMsg = async function sendAIMsg() {
        const input = document.getElementById('aiInputField');
        const msg = (input?.value || '').trim();
        if (!msg) return;

        const container = document.getElementById('aiMessagesContainer');
        container.querySelector('.ai-welcome')?.remove();

        const userDiv = document.createElement('div');
        userDiv.className = 'ai-msg user-msg';
        userDiv.innerHTML = `<div class="msg-avatar">👤</div><div class="msg-text">${escapeHtml(msg)}</div>`;
        container.appendChild(userDiv);
        input.value = '';

        const loading = document.createElement('div');
        loading.className = 'ai-msg ai-msg-bot loading';
        loading.innerHTML = `<div class="msg-avatar">🤖</div><div class="msg-text">Thinking...</div>`;
        container.appendChild(loading);
        container.scrollTop = container.scrollHeight;

        try {
            const language = localStorage.getItem('learnvaultx_ai_language') || 'english';
            const payload = await fetchJSON('/api/chatbot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: msg, mode: currentAIMode, language })
            });
            loading.remove();
            const aiDiv = document.createElement('div');
            aiDiv.className = 'ai-msg ai-msg-bot';
            aiDiv.innerHTML = `<div class="msg-avatar">🤖</div><div class="msg-text">${payload.reply || payload.raw || ''}</div>`;
            container.appendChild(aiDiv);
            container.scrollTop = container.scrollHeight;
        } catch (err) {
            loading.remove();
            const errDiv = document.createElement('div');
            errDiv.className = 'ai-msg ai-msg-bot error';
            errDiv.innerHTML = `<div class="msg-avatar">🤖</div><div class="msg-text">${escapeHtml(err.message || 'AI service error')}</div>`;
            container.appendChild(errDiv);
        }
    };

    window.showCreateClassModal = function showCreateClassModal() {
        document.getElementById('createClassModal').style.display = 'flex';
    };

    window.showUploadLectureModal = function showUploadLectureModal(classId, classTitle) {
        document.getElementById('uploadClassId').value = classId;
        document.getElementById('uploadClassTitle').textContent = `Class: ${classTitle}`;
        document.getElementById('uploadLectureModal').style.display = 'flex';
    };

    window.showCreateQuizModal = function showCreateQuizModal(classId, classTitle) {
        document.getElementById('quizClassId').value = classId;
        document.getElementById('quizClassTitle').textContent = `Class: ${classTitle}`;
        document.getElementById('questionsContainer').innerHTML = '';
        questionCount = 0;
        addQuestion();
        document.getElementById('createQuizModal').style.display = 'flex';
    };

    window.closeModal = function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.style.display = 'none';
    };

    window.createClass = async function createClass(event) {
        event.preventDefault();
        const title = (document.getElementById('className').value || '').trim();
        const description = (document.getElementById('classDescription').value || '').trim();
        if (!title || !description) {
            toastSafe('Title and description are required', 'warning');
            return;
        }

        try {
            const payload = await fetchJSON('/api/create_class', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, description })
            });

            classesCache.unshift({
                id: payload.class_id || (payload.data && payload.data.class_id),
                title,
                description,
                student_count: 0,
                lecture_count: 0
            });
            updateClassOptions();
            refreshClassGrid();
            updateStats();
            closeModal('createClassModal');
            document.getElementById('createClassForm').reset();
            toastSafe('Class created successfully', 'success');
        } catch (err) {
            toastSafe(err.message || 'Failed to create class', 'error');
        }
    };

    window.uploadLecture = async function uploadLecture(event) {
        event.preventDefault();
        const classId = document.getElementById('uploadClassId').value;
        const fileInput = document.getElementById('lectureFile');
        const file = fileInput.files && fileInput.files[0];
        if (!classId || !file) {
            toastSafe('Please select a file', 'warning');
            return;
        }

        const formData = new FormData();
        formData.append('class_id', classId);
        formData.append('file', file);
        try {
            await fetchJSON('/api/upload_lecture', {
                method: 'POST',
                body: formData
            });
            const classRef = classesCache.find(c => String(c.id) === String(classId));
            if (classRef) classRef.lecture_count = (classRef.lecture_count || 0) + 1;
            refreshClassGrid();
            updateStats();
            closeModal('uploadLectureModal');
            document.getElementById('uploadLectureForm').reset();
            toastSafe('Lecture uploaded successfully', 'success');
        } catch (err) {
            toastSafe(err.message || 'Failed to upload lecture', 'error');
        }
    };

    function validateQuestionBlock(block) {
        const question = (block.querySelector('.question-text')?.value || '').trim();
        const options = Array.from(block.querySelectorAll('.question-option')).map(opt => (opt.value || '').trim());
        const correct = Number(block.querySelector('.question-correct')?.value);
        if (!question || options.some(opt => !opt) || options.length < 2 || Number.isNaN(correct)) {
            return null;
        }
        return {
            question,
            options,
            correct,
            explanation: (block.querySelector('.question-explanation')?.value || '').trim()
        };
    }

    window.addQuestion = function addQuestion() {
        questionCount += 1;
        const container = document.getElementById('questionsContainer');
        const questionDiv = document.createElement('div');
        questionDiv.className = 'question-block';
        questionDiv.innerHTML = `
            <div class="question-header">
                <strong class="question-num">Question ${questionCount}</strong>
                <button type="button" class="btn-remove" onclick="this.closest('.question-block').remove()">Remove</button>
            </div>
            <div class="form-group">
                <label class="form-label">Question Text*</label>
                <input type="text" class="form-input question-text" required placeholder="Enter your question...">
            </div>
            <div class="form-group">
                <label class="form-label">Options (4 required)*</label>
                <input type="text" class="form-input question-option" required placeholder="Option 1">
                <input type="text" class="form-input question-option" required placeholder="Option 2" style="margin-top: 8px;">
                <input type="text" class="form-input question-option" required placeholder="Option 3" style="margin-top: 8px;">
                <input type="text" class="form-input question-option" required placeholder="Option 4" style="margin-top: 8px;">
            </div>
            <div class="form-group">
                <label class="form-label">Correct Answer (0-3)*</label>
                <select class="form-input question-correct" required>
                    <option value="0">Option 1</option>
                    <option value="1">Option 2</option>
                    <option value="2">Option 3</option>
                    <option value="3">Option 4</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Explanation (Optional)</label>
                <textarea class="form-input question-explanation" rows="2" placeholder="Explain why this is correct..."></textarea>
            </div>
        `;
        container.appendChild(questionDiv);
    };

    window.createQuiz = async function createQuiz(event) {
        event.preventDefault();
        const classId = document.getElementById('quizClassId').value;
        const title = (document.getElementById('quizTitle').value || '').trim();
        const description = (document.getElementById('quizDescription').value || '').trim();
        if (!classId || !title) {
            toastSafe('Class and quiz title are required', 'warning');
            return;
        }

        const blocks = Array.from(document.querySelectorAll('.question-block'));
        const questions = blocks.map(validateQuestionBlock).filter(Boolean);
        if (questions.length !== blocks.length || !questions.length) {
            toastSafe('Please complete all quiz question fields', 'warning');
            return;
        }

        try {
            await fetchJSON('/api/create_quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ class_id: classId, title, description, questions })
            });
            closeModal('createQuizModal');
            document.getElementById('createQuizForm').reset();
            toastSafe('Quiz created successfully', 'success');
            const quizzesEl = document.getElementById('totalQuizzes');
            if (quizzesEl) quizzesEl.textContent = Number(quizzesEl.textContent || '0') + 1;
        } catch (err) {
            toastSafe(err.message || 'Failed to create quiz', 'error');
        }
    };

    window.loadClassAnalytics = loadClassAnalytics;

    window.escapeHtml = function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    };

    window.toggleDesktopSidebar = function toggleDesktopSidebar() {
        const sidebar = document.getElementById('dashSidebar');
        if (!sidebar) return;
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('dashSidebarCollapsed', isCollapsed);
    };

    document.addEventListener('DOMContentLoaded', () => {
        const lastView = localStorage.getItem('lastTeacherView');
        if (lastView && document.getElementById(`${lastView}View`)) {
            switchView(lastView);
        } else {
            switchView('dashboard');
        }

        // Restore sidebar state
        const collapsed = localStorage.getItem('dashSidebarCollapsed') === 'true';
        if (collapsed) {
            document.getElementById('dashSidebar')?.classList.add('collapsed');
        }

        updateClassOptions();
        refreshClassGrid();
        updateStats();
        loadTeacherClasses();

        const aiInput = document.getElementById('aiInputField');
        if (aiInput) {
            aiInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    window.sendAIMsg();
                }
            });
        }
    });
})();
