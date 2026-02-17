/**
 * Chart.js Configuration for LearnVaultX Analytics
 * Midnight blue theme with neon cyan accents
 */

/**
 * Chart.js Configuration for LearnVaultX Analytics
 * Midnight blue theme with neon cyan accents
 */

// Chart.js default configuration
Chart.defaults.color = '#a0aec0';
Chart.defaults.borderColor = 'rgba(96, 165, 250, 0.1)';
Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

// Theme colors
// Theme colors - Vibrant & Futuristic
const chartColors = {
    primary: '#a855f7',      // Purple-500
    secondary: '#06b6d4',    // Cyan-500
    success: '#10b981',      // Emerald-500
    warning: '#f59e0b',      // Amber-500
    danger: '#ef4444',       // Red-500
    background: 'rgba(168, 85, 247, 0.1)',
    gradientStart: 'rgba(168, 85, 247, 0.4)',
    gradientEnd: 'rgba(6, 182, 212, 0.05)'
};

/**
 * Create a line chart for weekly trends
 */
function createWeeklyTrendChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, chartColors.gradientStart);
    gradient.addColorStop(1, chartColors.gradientEnd);

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.day),
            datasets: [{
                label: 'Score %',
                data: data.map(d => d.score),
                borderColor: '#c084fc', // Lighter purple
                backgroundColor: gradient,
                borderWidth: 3,
                fill: true,
                tension: 0.4, // Smooth curve
                pointRadius: 6,
                pointHoverRadius: 8,
                pointBackgroundColor: '#1e293b',
                pointBorderColor: '#c084fc',
                pointBorderWidth: 2
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
                    borderColor: 'rgba(192, 132, 252, 0.3)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function (context) {
                            return `Score: ${context.parsed.y}%`;
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
            },
            interaction: {
                mode: 'index',
                intersect: false,
            }
        }
    });
}

/**
 * Create a bar chart for topic breakdown
 */
function createTopicBreakdownChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    const normalized = Array.isArray(data)
        ? data.map(item => ({ topic: item.topic, score: item.score }))
        : Object.keys(data || {}).map(key => ({ topic: key, score: data[key].score }));
    const topics = normalized.map(item => item.topic);
    const scores = normalized.map(item => Number(item.score || 0));

    // Generate an array of colors for bars
    const bgColors = scores.map((_, i) => {
        const colors = ['#a855f7', '#06b6d4', '#ec4899', '#8b5cf6', '#3b82f6'];
        return colors[i % colors.length];
    });

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: topics,
            datasets: [{
                label: 'Score %',
                data: scores,
                backgroundColor: bgColors,
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
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function (context) {
                            return `Score: ${context.parsed.y}%`;
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
}

/**
 * Create a donut chart for completion stats
 */
function createCompletionChart(canvasId, completed, pending) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Completed', 'Pending'],
            datasets: [{
                data: [completed, pending],
                backgroundColor: [chartColors.success, chartColors.warning],
                borderColor: '#1e293b',
                borderWidth: 3,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        font: { size: 14 },
                        usePointStyle: true,
                        pointStyle: 'circle',
                        color: '#94a3b8'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: chartColors.primary,
                    bodyColor: '#e2e8f0',
                    borderColor: chartColors.primary,
                    borderWidth: 1,
                    padding: 12
                }
            }
        }
    });
}

/**
 * Create a horizontal bar chart for performance distribution
 */
function createPerformanceDistributionChart(canvasId, distribution) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    const labels = Object.keys(distribution);
    const values = Object.values(distribution);

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Students',
                data: values,
                backgroundColor: [
                    chartColors.danger,
                    chartColors.warning,
                    '#f59e0b',
                    chartColors.primary,
                    chartColors.success
                ],
                borderColor: '#1e293b',
                borderWidth: 2,
                borderRadius: 8
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: chartColors.primary,
                    bodyColor: '#e2e8f0',
                    borderColor: chartColors.primary,
                    borderWidth: 1,
                    padding: 12
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(96, 165, 250, 0.1)',
                        drawBorder: false
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

/**
 * Create a line chart for participation trend
 */
function createParticipationTrendChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    const normalized = (data || []).map((d) => ({
        day: d.day || d.date,
        participation_percent: d.participation_percent != null ? d.participation_percent : d.count
    }));

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: normalized.map(d => d.day),
            datasets: [{
                label: 'Participation %',
                data: normalized.map(d => d.participation_percent),
                borderColor: chartColors.success,
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointBackgroundColor: chartColors.success,
                pointBorderColor: '#1e293b',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: chartColors.success,
                    bodyColor: '#e2e8f0',
                    borderColor: chartColors.success,
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function (context) {
                            return 'Participation: ' + context.parsed.y + '%';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(96, 165, 250, 0.1)',
                        drawBorder: false
                    },
                    ticks: {
                        callback: function (value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}
