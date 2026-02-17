/**
 * Learning Path Logic
 */

let allSubjects = []; // populated from window.__STUDENT_CLASSES__ or API

function initLearningPath() {
    console.log("Initializing Learning Path...");
    // Populate Subject Dropdown
    const select = document.getElementById('lpSubjectSelect');
    if (!select) return;

    // Clear existing (keep first)
    select.innerHTML = '<option value="" disabled selected>-- Choose a Class --</option>';

    if (window.__STUDENT_CLASSES__ && window.__STUDENT_CLASSES__.length > 0) {
        window.__STUDENT_CLASSES__.forEach(cls => {
            const opt = document.createElement('option');
            opt.value = cls.id;
            opt.textContent = cls.title;
            select.appendChild(opt);
        });

        // Auto-select first if available
        if (window.__STUDENT_CLASSES__.length > 0) {
            select.value = window.__STUDENT_CLASSES__[0].id;
            loadLearningPath(window.__STUDENT_CLASSES__[0].id);
        }
    } else {
        // Handle no classes
        const opt = document.createElement('option');
        opt.disabled = true;
        opt.textContent = "No active classes found";
        select.appendChild(opt);
    }
}

async function loadLearningPath(classId) {
    if (!classId) return;

    const timeline = document.getElementById('lpTimeline');
    const banner = document.getElementById('lpNextActionBanner');

    // Show Loading
    timeline.innerHTML = `
        <div class="loading-box">
            <div class="loading-spinner"></div>
            <p class="loading-text">Loading learning path...</p>
        </div>
    `;
    banner.style.display = 'none';

    try {
        const response = await fetch(`/api/learning-path/${classId}`);
        const data = await response.json();

        if (data.success) {
            renderLearningPath(data.modules);
            renderNextAction(data.next_action);
        } else {
            timeline.innerHTML = `<div class="empty-state-box"><p>${data.message || 'Failed to load path'}</p></div>`;
        }
    } catch (error) {
        console.error("Error loading path:", error);
        timeline.innerHTML = `<div class="empty-state-box"><p>Error loading data. Please try again.</p></div>`;
    }
}

function renderLearningPath(modules) {
    const timeline = document.getElementById('lpTimeline');
    timeline.innerHTML = '';

    if (!modules || modules.length === 0) {
        timeline.innerHTML = `
            <div class="empty-state-box">
                <div class="empty-ico">🛣️</div>
                <h3 class="empty-heading">No modules found</h3>
                <p class="empty-desc">This subject doesn't have a learning path configured yet.</p>
            </div>
        `;
        return;
    }

    modules.forEach(mod => {
        const isLocked = mod.status === 'LOCKED';
        const isCompleted = mod.status === 'COMPLETED';
        const isInProgress = mod.status === 'IN_PROGRESS'; // or UNLOCKED but not started

        let cardClass = '';
        if (mod.needs_revision) {
            cardClass += ' needs-revision';
        }

        const statusText = isLocked ? 'Locked' : (isCompleted ? 'Completed' : 'In Progress');

        // Determine available quiz/actions
        let actionsHtml = '';
        if (!isLocked) {
            let btnText = isCompleted ? 'Retake Quiz' : 'Start Quiz';
            if (mod.needs_revision) btnText = 'Review & Retake';

            actionsHtml = `
                <div class="lp-card-actions">
                    <button class="lp-action-btn lp-btn-primary" onclick="startModuleQuiz(${mod.id}, '${mod.title}', ${mod.is_locked}, ${mod.quiz_id || 'null'})">
                        ${btnText}
                    </button>
                </div>
            `;
        }

        // Revision Alert HTML
        let revisionHtml = '';
        if (mod.needs_revision) {
            revisionHtml = `
                <div class="lp-revision-alert">
                    <div class="lp-rev-icon">⚠️</div>
                    <div class="lp-rev-content">
                        <span class="lp-rev-title">Needs Revision</span>
                        <div class="lp-rev-text">${mod.revision_reason || 'You struggled with this topic.'}</div>
                    </div>
                </div>
            `;
        }

        const html = `
            <div class="lp-module-card ${cardClass}" id="mod-${mod.id}">
                <div class="lp-module-header">
                    <div class="lp-mod-title">${mod.title}</div>
                    <div class="lp-mod-status ${mod.needs_revision ? 'revision' : ''}">${mod.needs_revision ? 'Needs Revision' : statusText}</div>
                </div>
                <div class="lp-mod-desc">${mod.description || 'No description available.'}</div>
                
                ${revisionHtml}

                <div class="lp-progress-area">
                    <div class="lp-prog-label">
                        <span>Progress</span>
                        <span>${Math.round(mod.completion_percent)}%</span>
                    </div>
                    <div class="lp-prog-bar-bg">
                        <div class="lp-prog-bar-fill" style="width: ${mod.completion_percent}%"></div>
                    </div>
                </div>
                
                ${actionsHtml}
            </div>
        `;
        timeline.innerHTML += html;
    });
}

function renderNextAction(action) {
    const banner = document.getElementById('lpNextActionBanner');
    if (action) {
        document.getElementById('lpNextActionText').textContent = action.message;
        const btn = document.getElementById('lpNextActionBtn');
        btn.onclick = () => {
            // Action could be 'Start Quiz'
            // We need to know which quiz. For now, we scroll to module or open quiz selector?
            // "action" object logic in backend was simplified.
            // Let's scroll to the module card
            const modCard = document.getElementById(`mod-${action.module_id}`);
            if (modCard) {
                modCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                // Highlight?
                modCard.style.border = "2px solid #a855f7";
                setTimeout(() => modCard.style.border = "", 2000);
            }
        };
        banner.style.display = 'flex';
    } else {
        banner.style.display = 'none';
    }
}

function startModuleQuiz(moduleId, moduleTitle, isLocked, quizId) {
    if (isLocked) return;

    if (quizId) {
        // Redirect to quiz page
        window.location.href = `/student/quiz/${quizId}`;
    } else {
        alert("No quiz available for this module yet.");
    }
}

// Global exposure
window.initLearningPath = initLearningPath;
window.loadLearningPath = loadLearningPath;
