/**
 * Chart.js Configuration for LearnVaultX Analytics
 * Midnight blue theme with neon cyan accents
 */

// Chart.js default configuration
Chart.defaults.color = '#a0aec0';
Chart.defaults.borderColor = 'rgba(96, 165, 250, 0.1)';
Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

// Theme colors
const chartColors = {
    primary: '#60a5fa',      // Neon cyan/blue
    secondary: '#3b82f6',    // Darker blue
    success: '#10b981',      // Green
    warning: '#f59e0b',      // Orange
    danger: '#ef4444',       // Red
    background: 'rgba(96, 165, 250, 0.1)',
    gradient1: '#60a5fa',
    gradient2: '#3b82f6'
};

/**
 * Create a line chart for weekly trends
 */
function createWeeklyTrendChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(96, 165, 250, 0.3)');
    gradient.addColorStop(1, 'rgba(96, 165, 250, 0.0)');
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.day),
            datasets: [{
                label: 'Score %',
                data: data.map(d => d.score),
                borderColor: chartColors.primary,
                backgroundColor: gradient,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointBackgroundColor: chartColors.primary,
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
                    titleColor: chartColors.primary,
                    bodyColor: '#e2e8f0',
                    borderColor: chartColors.primary,
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return 'Score: ' + context.parsed.y + '%';
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
                        callback: function(value) {
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

/**
 * Create a bar chart for topic breakdown
 */
function createTopicBreakdownChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    const topics = Object.keys(data);
    const scores = topics.map(t => data[t].score);
    
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: topics,
            datasets: [{
                label: 'Score %',
                data: scores,
                backgroundColor: chartColors.primary,
                borderColor: chartColors.secondary,
                borderWidth: 2,
                borderRadius: 8,
                barThickness: 40
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
                    titleColor: chartColors.primary,
                    bodyColor: '#e2e8f0',
                    borderColor: chartColors.primary,
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            return 'Score: ' + context.parsed.y + '%';
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
                        callback: function(value) {
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
                        font: {
                            size: 14
                        },
                        usePointStyle: true,
                        pointStyle: 'circle'
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
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.day),
            datasets: [{
                label: 'Participation %',
                data: data.map(d => d.participation_percent),
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
                        label: function(context) {
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
                        callback: function(value) {
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
