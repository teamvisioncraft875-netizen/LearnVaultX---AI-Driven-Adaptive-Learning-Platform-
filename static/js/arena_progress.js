/* ═══════════════════════════════════════════════════════════
   ARENA PROGRESS — Chart.js Initialization
   responsive: false — Chart.js does NOT watch for resizes.
   Canvas dimensions set once by JS. No feedback loop possible.
   ═══════════════════════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", function () {
    if (window.__arenaProgressChartsLoaded) return;
    window.__arenaProgressChartsLoaded = true;
    initArenaProgressCharts();
});

function initArenaProgressCharts() {
    var dataEl = document.getElementById('ap-chart-data');
    if (!dataEl) return;

    var labels, scores, speeds;
    try {
        labels = JSON.parse(dataEl.dataset.labels || '[]');
        scores = JSON.parse(dataEl.dataset.scores || '[]');
        speeds = JSON.parse(dataEl.dataset.speeds || '[]');
    } catch (e) {
        console.error('[ArenaProgress] Parse error:', e);
        return;
    }

    if (labels.length === 0) return;

    Chart.defaults.color = '#aaa';
    Chart.defaults.borderColor = 'rgba(255,255,255,0.08)';

    // Destroy any existing instances
    if (window.scoreChartInstance) { window.scoreChartInstance.destroy(); window.scoreChartInstance = null; }
    if (window.speedChartInstance) { window.speedChartInstance.destroy(); window.speedChartInstance = null; }

    // ── Helper: create canvas with FIXED pixel dimensions ──
    function buildCanvas(boxId) {
        var box = document.getElementById(boxId);
        if (!box) return null;
        // Clear any existing content
        box.innerHTML = '';
        var w = box.offsetWidth || 500;
        var h = 300;
        var c = document.createElement('canvas');
        c.width = w;
        c.height = h;
        c.style.cssText = 'display:block;width:' + w + 'px;height:' + h + 'px;';
        box.appendChild(c);
        return c;
    }

    // ── Score Chart ──
    var scoreCanvas = buildCanvas('apScoreChartBox');
    if (scoreCanvas) {
        window.scoreChartInstance = new Chart(scoreCanvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Accuracy %',
                    data: scores,
                    borderColor: '#6C5DD3',
                    backgroundColor: 'rgba(108, 93, 211, 0.15)',
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: '#fff',
                    pointRadius: 4,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: false,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: true, position: 'top', labels: { boxWidth: 12 } } },
                scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + '%'; } } } }
            }
        });
    }

    // ── Speed Chart ──
    var speedCanvas = buildCanvas('apSpeedChartBox');
    if (speedCanvas) {
        window.speedChartInstance = new Chart(speedCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Avg Time (s)',
                    data: speeds,
                    backgroundColor: 'rgba(255, 171, 0, 0.7)',
                    borderColor: '#FFAB00',
                    borderWidth: 1,
                    borderRadius: 4,
                    maxBarThickness: 40
                }]
            },
            options: {
                responsive: false,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: true, position: 'top', labels: { boxWidth: 12 } } },
                scales: { y: { beginAtZero: true, ticks: { callback: function (v) { return v + 's'; } } } }
            }
        });
    }

    console.log('[ArenaProgress] Charts created (responsive:false, fixed px).');
}
