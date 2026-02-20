
document.addEventListener('DOMContentLoaded', () => {
    // 1. Load Leaderboard
    loadLeaderboard();

    // 2. Initialize Visuals (if any specific JS needed for canvas/svg)
    // SVG paths are CSS animated, so mostly handled there.
});

/* ─── MISSION LOGIC ────────────────────────────────────── */
const MISSION_META = {
    'daily_challenge': { title: 'Daily Challenge', desc: '10 questions, 10 minutes. Earn +50 XP and keep your streak alive!', xp: 50, time: '10m', url: '/arena/start/daily' },
    'adaptive_mock': { title: 'Adaptive Mock', desc: 'AI-generated quiz based on your performance. Difficulty adjusts automatically.', xp: 30, time: '15m', url: '/arena/start/mock' },
    'weakness_fix': { title: 'Weakness Fix', desc: 'Target your weakest topics to boost your readiness score.', xp: 40, time: '12m', url: '/arena/start/mock' },
    'speed_run': { title: 'Speed Run', desc: 'Race against the clock! High speed required.', xp: 40, time: '5m', url: '/arena/start/mock' },
    'boss_fight': { title: 'BOSS FIGHT', desc: 'The ultimate test. 15 Hard questions. Conquer this to prove your mastery.', xp: 200, time: '12m', url: '/arena/boss_fight' }
};

function handleMissionClick(missionId, status, type) {
    if (status === 'locked') {
        showToast('🔒 This mission is locked! Complete previous missions to unlock.');
        return;
    }

    // If completed daily, show message (unless we want to allow replay without rewards? No, usually block)
    if (missionId === 'daily_challenge' && status === 'completed') {
        showToast('✅ Daily Challenge already completed! Come back tomorrow.');
        return;
    }

    const meta = MISSION_META[missionId];
    if (!meta) return;

    // Populate Modal
    document.getElementById('modalTitle').innerText = meta.title;
    document.getElementById('modalDesc').innerText = meta.desc;
    document.getElementById('modalXP').innerText = meta.xp;
    document.getElementById('modalTime').innerText = meta.time;

    // Configure Start Button
    const btn = document.getElementById('modalStartBtn');
    btn.onclick = function (e) {
        e.preventDefault();
        startMission(meta.url, type);
    };
    btn.removeAttribute('href'); // Ensure it doesn't navigate as a link

    openModal('missionModal');
}

function startMission(url, type) {
    const btn = document.getElementById('modalStartBtn');
    const originalText = btn.innerText;
    btn.innerText = 'Starting...';
    btn.disabled = true;

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: type }) // Send mode if needed
    })
        .then(res => res.json())
        .then(data => {
            if (data.success && data.redirect) {
                window.location.href = data.redirect;
            } else {
                alert(data.error || 'Failed to start mission.');
                btn.innerText = originalText;
                btn.disabled = false;
            }
        })
        .catch(err => {
            console.error('Start Mission Error:', err);
            alert('Connection error. Please try again.');
            btn.innerText = originalText;
            btn.disabled = false;
        });
}

/* ─── MODAL SYSTEM ─────────────────────────────────────── */
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.style.display = 'none';
    }
}

// Close on outside click
window.onclick = function (event) {
    if (event.target.classList.contains('game-modal')) {
        event.target.style.display = 'none';
    }
}

function showToast(msg) {
    const toast = document.querySelector('.map-info-toast');
    // const originalText = toast.innerHTML; // Don't rely on innerHTML restoration as it might change

    toast.innerHTML = `<span class="info-icon">⚠️</span> ${msg}`;
    toast.classList.add('error-pulse');

    setTimeout(() => {
        toast.innerHTML = `<span class="info-icon">💡</span> Select a mission to start your journey.`;
        toast.classList.remove('error-pulse');
    }, 3000);
}

/* ─── PROFILE LOGIC ────────────────────────────────────── */
function openProfileModal() {
    openModal('profileModal');
}

function saveProfileFromModal() {
    const exam = document.getElementById('modalExam').value;
    const subject = document.getElementById('modalSubject').value;

    fetch('/arena/set_exam_profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exam, subject })
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                closeModal('profileModal');
                location.reload();
            } else {
                alert('Error saving profile');
            }
        })
        .catch(err => console.error(err));
}

/* ─── LEADERBOARD LOGIC ────────────────────────────────── */
function loadLeaderboard() {
    const container = document.getElementById('leaderboardContainer');

    fetch('/arena/api/leaderboard')
        .then(res => res.json())
        .then(data => {
            if (data.success && data.leaders) {
                let html = `<h3>Top Agents</h3><div class="leaderboard-list">`;

                data.leaders.forEach((l, index) => {
                    const badge = l.badge_icon || '👤';
                    html += `
                <div class="lb-row">
                    <span class="lb-rank">#${index + 1}</span>
                    <span class="lb-avatar">${badge}</span>
                    <div class="lb-info">
                        <span class="lb-name">${l.username}</span>
                        <span class="lb-xp">${l.xp_total} XP</span>
                    </div>
                </div>`;
                });

                html += `</div>`;
                container.innerHTML = html;
            } else {
                container.innerHTML = '<h3>Top Agents</h3><p class="empty-text">No data available.</p>';
            }
        })
        .catch(err => {
            console.error('Leaderboard load error:', err);
            container.innerHTML = '<h3>Top Agents</h3><p class="empty-text">Failed to load.</p>';
        });
}
