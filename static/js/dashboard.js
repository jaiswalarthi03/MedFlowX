// Dashboard functionality for CDA-to-FHIR Converter

let dashboardCharts = {};

document.addEventListener('DOMContentLoaded', function() {
    loadDashboardData();
});

function loadDashboardData() {
    showLoading();
    
    fetch('/api/dashboard-data')
        .then(response => response.json())
        .then(data => {
            hideLoading();
            populateDashboard(data);
        })
        .catch(error => {
            hideLoading();
            showError();
            console.error('Dashboard error:', error);
        });
}

function showLoading() {
    document.getElementById('dashboard-loading').classList.remove('d-none');
    document.getElementById('dashboard-content').classList.add('d-none');
    document.getElementById('dashboard-error').classList.add('d-none');
}

function hideLoading() {
    document.getElementById('dashboard-loading').classList.add('d-none');
}

function showError() {
    document.getElementById('dashboard-error').classList.remove('d-none');
    document.getElementById('dashboard-content').classList.add('d-none');
}

function populateDashboard(data) {
    // Show dashboard content
    document.getElementById('dashboard-content').classList.remove('d-none');
    
    // Populate metrics
    populateMetrics(data.processing_stats, data.fhir_resources);
    
    // Create charts
    createTimelineChart(data.processing_timeline);
    createEntityChart(data.entity_extraction);
    createSuccessRateChart(data.conversion_success_rate);
    createFHIRResourcesChart(data.fhir_resources);
    
    // Populate recent activity
    populateRecentActivity(data.recent_activity);
}

function populateMetrics(processingStats, fhirResources) {
    // Calculate total FHIR resources
    const totalFhirResources = Object.values(fhirResources).reduce((sum, count) => sum + count, 0);
    
    // Update metric cards
    document.getElementById('total-documents').textContent = processingStats.total_documents;
    document.getElementById('successful-conversions').textContent = processingStats.successful_conversions;
    document.getElementById('avg-processing-time').textContent = processingStats.processing_time_avg.toFixed(1);
    document.getElementById('total-fhir-resources').textContent = totalFhirResources;
}

function createTimelineChart(timelineData) {
    const ctx = document.getElementById('timelineChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (dashboardCharts.timeline) {
        dashboardCharts.timeline.destroy();
    }
    
    dashboardCharts.timeline = new Chart(ctx, {
        type: 'line',
        data: {
            labels: timelineData.map(item => {
                const date = new Date(item.date);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            }),
            datasets: [{
                label: 'Documents Processed',
                data: timelineData.map(item => item.documents),
                borderColor: '#C8A8E9',
                backgroundColor: 'rgba(200, 168, 233, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#C8A8E9',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        color: '#6c757d'
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#6c757d'
                    }
                }
            },
            elements: {
                point: {
                    hoverRadius: 8
                }
            }
        }
    });
}

function createEntityChart(entityData) {
    const ctx = document.getElementById('entityChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (dashboardCharts.entity) {
        dashboardCharts.entity.destroy();
    }
    
    const colors = ['#C8A8E9', '#A788C7', '#E8D5F2', '#9B7BB8'];
    
    dashboardCharts.entity = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(entityData).map(key => 
                key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())
            ),
            datasets: [{
                data: Object.values(entityData),
                backgroundColor: colors,
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true,
                        color: '#6c757d'
                    }
                }
            },
            cutout: '60%'
        }
    });
}

function createSuccessRateChart(successRateData) {
    const ctx = document.getElementById('successRateChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (dashboardCharts.successRate) {
        dashboardCharts.successRate.destroy();
    }
    
    dashboardCharts.successRate = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: successRateData.map(item => item.month),
            datasets: [{
                label: 'Success Rate (%)',
                data: successRateData.map(item => item.success_rate),
                backgroundColor: 'rgba(200, 168, 233, 0.8)',
                borderColor: '#C8A8E9',
                borderWidth: 1,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        color: '#6c757d',
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#6c757d'
                    }
                }
            }
        }
    });
}

function createFHIRResourcesChart(fhirData) {
    const ctx = document.getElementById('fhirResourcesChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (dashboardCharts.fhirResources) {
        dashboardCharts.fhirResources.destroy();
    }
    
    const colors = [
        '#C8A8E9',
        '#A788C7',
        '#E8D5F2',
        '#9B7BB8',
        '#D4C2E8'
    ];
    
    dashboardCharts.fhirResources = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(fhirData).map(key => 
                key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())
            ),
            datasets: [{
                label: 'Resource Count',
                data: Object.values(fhirData),
                backgroundColor: colors,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        color: '#6c757d'
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#6c757d',
                        maxRotation: 45
                    }
                }
            }
        }
    });
}

function populateRecentActivity(activityData) {
    const activityList = document.getElementById('recent-activity-list');
    
    if (!activityData || activityData.length === 0) {
        activityList.innerHTML = `
            <div class="text-center py-4">
                <i data-feather="inbox" style="width: 48px; height: 48px; color: #dee2e6;"></i>
                <p class="text-muted mt-2">No recent activity</p>
            </div>
        `;
        feather.replace();
        return;
    }
    
    const activityHTML = activityData.map(activity => `
        <div class="activity-item slide-in">
            <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1">
                    <h6 class="mb-1">${activity.action}</h6>
                    <p class="text-muted mb-1">${activity.patient}</p>
                    <small class="text-muted">${activity.timestamp}</small>
                </div>
                <span class="activity-status ${activity.status}">
                    ${activity.status}
                </span>
            </div>
        </div>
    `).join('');
    
    activityList.innerHTML = activityHTML;
}

function refreshDashboard() {
    // Add a brief loading state to the refresh button
    const refreshBtn = document.querySelector('button[onclick="refreshDashboard()"]');
    const originalHTML = refreshBtn.innerHTML;
    
    refreshBtn.innerHTML = '<i data-feather="refresh-cw" class="me-1 fa-spin"></i> Refreshing...';
    refreshBtn.disabled = true;
    
    // Reload dashboard data
    loadDashboardData();
    
    // Reset button after 2 seconds
    setTimeout(() => {
        refreshBtn.innerHTML = originalHTML;
        refreshBtn.disabled = false;
        feather.replace();
    }, 2000);
}

// Utility function to format numbers
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// Handle window resize for charts
window.addEventListener('resize', function() {
    Object.values(dashboardCharts).forEach(chart => {
        if (chart && typeof chart.resize === 'function') {
            chart.resize();
        }
    });
});
