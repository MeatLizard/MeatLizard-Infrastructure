/**
 * Analytics Dashboard JavaScript
 * 
 * Handles chart rendering, real-time updates, and user interactions
 * for the video analytics dashboard.
 */

class AnalyticsDashboard {
    constructor() {
        this.charts = {};
        this.realtimeInterval = null;
        this.currentVideoId = null;
        this.currentTimeframe = '30d';
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // Timeframe selector
        const timeframeSelector = document.getElementById('timeframe-selector');
        if (timeframeSelector) {
            timeframeSelector.addEventListener('change', (e) => {
                this.changeTimeframe(e.target.value);
            });
        }
        
        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.refreshData();
            });
        }
        
        // Export button
        const exportBtn = document.getElementById('export-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.showExportModal();
            });
        }
        
        // Export modal handlers
        this.initializeExportModal();
    }
    
    initializeExportModal() {
        const modal = document.getElementById('export-modal');
        const closeBtn = document.querySelector('.modal-close');
        const cancelBtn = document.getElementById('export-cancel');
        const confirmBtn = document.getElementById('export-confirm');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        }
        
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        }
        
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => {
                this.exportData();
                modal.style.display = 'none';
            });
        }
        
        // Close modal when clicking outside
        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }
    
    initializeDashboard(dashboardData, timeframe) {
        this.currentTimeframe = timeframe;
        
        // Initialize charts
        this.createViewsChart(dashboardData.charts?.views_over_time || []);
        this.createWatchTimeChart(dashboardData.charts?.watch_time_over_time || []);
        
        // Format activity timestamps
        this.formatActivityTimestamps();
    }
    
    initializeVideoAnalytics(videoData, videoId, timeframe) {
        this.currentVideoId = videoId;
        this.currentTimeframe = timeframe;
        
        // Initialize charts
        this.createViewsOverTimeChart(videoData.views_over_time || []);
        this.createRetentionChart(videoData.audience_retention || []);
        this.createQualityChart(videoData.quality_metrics?.quality_distribution || {});
        this.createEngagementChart(videoData.engagement_timeline || []);
        
        // Start real-time updates
        this.startRealtimeUpdates();
        
        // Format timestamps
        this.formatActivityTimestamps();
    }
    
    createViewsChart(data) {
        const ctx = document.getElementById('viewsChart');
        if (!ctx || !data.length) return;
        
        this.charts.views = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => this.formatDate(d.date)),
                datasets: [{
                    label: 'Views',
                    data: data.map(d => d.views),
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    createWatchTimeChart(data) {
        const ctx = document.getElementById('watchTimeChart');
        if (!ctx || !data.length) return;
        
        this.charts.watchTime = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => this.formatDate(d.date)),
                datasets: [{
                    label: 'Watch Time (hours)',
                    data: data.map(d => d.watch_time_hours),
                    backgroundColor: '#28a745',
                    borderColor: '#1e7e34',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value + 'h';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    createViewsOverTimeChart(data) {
        const ctx = document.getElementById('viewsOverTimeChart');
        if (!ctx || !data.length) return;
        
        this.charts.viewsOverTime = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => this.formatDateTime(d.timestamp)),
                datasets: [{
                    label: 'Views',
                    data: data.map(d => d.views),
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    createRetentionChart(data) {
        const ctx = document.getElementById('retentionChart');
        if (!ctx || !data.length) return;
        
        this.charts.retention = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => d.percentage + '%'),
                datasets: [{
                    label: 'Retention Rate',
                    data: data.map(d => d.retention_rate),
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    createQualityChart(data) {
        const ctx = document.getElementById('qualityChart');
        if (!ctx || !Object.keys(data).length) return;
        
        const qualities = Object.keys(data);
        const counts = Object.values(data);
        
        this.charts.quality = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: qualities,
                datasets: [{
                    data: counts,
                    backgroundColor: [
                        '#007bff',
                        '#28a745',
                        '#ffc107',
                        '#dc3545',
                        '#6f42c1',
                        '#fd7e14'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    createEngagementChart(data) {
        const ctx = document.getElementById('engagementChart');
        if (!ctx || !data.length) return;
        
        // Group engagement events by type
        const likes = data.filter(d => d.type === 'like');
        const dislikes = data.filter(d => d.type === 'dislike');
        const comments = data.filter(d => d.type === 'comment');
        
        // Create cumulative data
        const timestamps = [...new Set(data.map(d => d.timestamp))].sort();
        const likesData = this.createCumulativeData(likes, timestamps);
        const dislikesData = this.createCumulativeData(dislikes, timestamps);
        const commentsData = this.createCumulativeData(comments, timestamps);
        
        this.charts.engagement = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timestamps.map(t => this.formatDateTime(t)),
                datasets: [
                    {
                        label: 'Likes',
                        data: likesData,
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Dislikes',
                        data: dislikesData,
                        borderColor: '#dc3545',
                        backgroundColor: 'rgba(220, 53, 69, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Comments',
                        data: commentsData,
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    createCumulativeData(events, timestamps) {
        let cumulative = 0;
        return timestamps.map(timestamp => {
            const eventsAtTime = events.filter(e => e.timestamp <= timestamp).length;
            cumulative = eventsAtTime;
            return cumulative;
        });
    }
    
    startRealtimeUpdates() {
        if (!this.currentVideoId) return;
        
        this.realtimeInterval = setInterval(() => {
            this.updateRealtimeMetrics();
        }, 30000); // Update every 30 seconds
        
        // Initial update
        this.updateRealtimeMetrics();
    }
    
    async updateRealtimeMetrics() {
        if (!this.currentVideoId) return;
        
        try {
            const response = await fetch(`/dashboard/api/realtime/${this.currentVideoId}`);
            const result = await response.json();
            
            if (result.success) {
                const data = result.data;
                
                // Update active viewers
                const activeViewersEl = document.getElementById('active-viewers');
                if (activeViewersEl) {
                    activeViewersEl.textContent = data.active_viewers || 0;
                }
                
                // Update recent events
                const recentEventsEl = document.getElementById('recent-events');
                if (recentEventsEl) {
                    recentEventsEl.textContent = data.events_last_5min || 0;
                }
                
                // Update indicator
                const indicator = document.getElementById('realtime-indicator');
                if (indicator) {
                    indicator.style.background = '#28a745';
                }
            }
        } catch (error) {
            console.error('Failed to update real-time metrics:', error);
            
            // Update indicator to show error
            const indicator = document.getElementById('realtime-indicator');
            if (indicator) {
                indicator.style.background = '#dc3545';
            }
        }
    }
    
    async changeTimeframe(newTimeframe) {
        this.currentTimeframe = newTimeframe;
        
        // Update URL
        const url = new URL(window.location);
        url.searchParams.set('timeframe', newTimeframe);
        window.history.pushState({}, '', url);
        
        // Refresh data
        await this.refreshData();
    }
    
    async refreshData() {
        try {
            let endpoint;
            if (this.currentVideoId) {
                endpoint = `/dashboard/api/video/${this.currentVideoId}/data?timeframe=${this.currentTimeframe}`;
            } else {
                endpoint = `/dashboard/api/data?timeframe=${this.currentTimeframe}`;
            }
            
            const response = await fetch(endpoint);
            const result = await response.json();
            
            if (result.success) {
                // Destroy existing charts
                Object.values(this.charts).forEach(chart => {
                    if (chart) chart.destroy();
                });
                this.charts = {};
                
                // Reinitialize with new data
                if (this.currentVideoId) {
                    this.initializeVideoAnalytics(result.data, this.currentVideoId, this.currentTimeframe);
                } else {
                    this.initializeDashboard(result.data, this.currentTimeframe);
                }
                
                // Update metric cards
                this.updateMetricCards(result.data);
            }
        } catch (error) {
            console.error('Failed to refresh data:', error);
            this.showError('Failed to refresh data. Please try again.');
        }
    }
    
    updateMetricCards(data) {
        // Update overview metrics
        if (data.overview) {
            this.updateMetricCard('total-videos', data.overview.total_videos);
            this.updateMetricCard('total-views', data.overview.total_views);
            this.updateMetricCard('total-watch-time', data.overview.total_watch_time_hours);
            this.updateMetricCard('total-likes', data.overview.total_likes);
        }
        
        // Update basic metrics for video analytics
        if (data.basic_metrics) {
            this.updateMetricCard('video-views', data.basic_metrics.total_views);
            this.updateMetricCard('video-watch-time', data.basic_metrics.total_watch_time_seconds / 3600);
            this.updateMetricCard('video-completion', data.basic_metrics.completion_rate_percent);
        }
    }
    
    updateMetricCard(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = typeof value === 'number' ? this.formatNumber(value) : value;
        }
    }
    
    showExportModal() {
        const modal = document.getElementById('export-modal');
        if (modal) {
            modal.style.display = 'block';
        }
    }
    
    async exportData() {
        if (!this.currentVideoId) {
            this.showError('No video selected for export');
            return;
        }
        
        try {
            const format = document.querySelector('input[name="export-format"]:checked').value;
            const url = `/dashboard/api/export/${this.currentVideoId}?format=${format}&timeframe=${this.currentTimeframe}`;
            
            if (format === 'csv') {
                // Download CSV file
                const link = document.createElement('a');
                link.href = url;
                link.download = `video_${this.currentVideoId}_analytics.csv`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } else {
                // Download JSON file
                const response = await fetch(url);
                const result = await response.json();
                
                if (result.success) {
                    const blob = new Blob([JSON.stringify(result.data, null, 2)], {
                        type: 'application/json'
                    });
                    const link = document.createElement('a');
                    link.href = URL.createObjectURL(blob);
                    link.download = `video_${this.currentVideoId}_analytics.json`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    URL.revokeObjectURL(link.href);
                }
            }
        } catch (error) {
            console.error('Failed to export data:', error);
            this.showError('Failed to export data. Please try again.');
        }
    }
    
    formatActivityTimestamps() {
        const timeElements = document.querySelectorAll('.activity-time');
        timeElements.forEach(el => {
            const timestamp = el.textContent;
            if (timestamp && timestamp !== '-') {
                el.textContent = this.formatRelativeTime(timestamp);
            }
        });
    }
    
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric'
        });
    }
    
    formatDateTime(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit'
        });
    }
    
    formatRelativeTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    }
    
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toLocaleString();
    }
    
    showError(message) {
        // Create or update error notification
        let errorEl = document.getElementById('error-notification');
        if (!errorEl) {
            errorEl = document.createElement('div');
            errorEl.id = 'error-notification';
            errorEl.className = 'error-notification';
            document.body.appendChild(errorEl);
        }
        
        errorEl.textContent = message;
        errorEl.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorEl.style.display = 'none';
        }, 5000);
    }
    
    destroy() {
        // Clean up intervals
        if (this.realtimeInterval) {
            clearInterval(this.realtimeInterval);
        }
        
        // Destroy charts
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
    }
}

// Global instance
let dashboard = null;

// Initialize functions
function initializeDashboard(dashboardData, timeframe) {
    if (dashboard) {
        dashboard.destroy();
    }
    dashboard = new AnalyticsDashboard();
    dashboard.initializeDashboard(dashboardData, timeframe);
}

function initializeVideoAnalytics(videoData, videoId, timeframe) {
    if (dashboard) {
        dashboard.destroy();
    }
    dashboard = new AnalyticsDashboard();
    dashboard.initializeVideoAnalytics(videoData, videoId, timeframe);
}

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (dashboard) {
        dashboard.destroy();
    }
});

// Error notification styles
const errorStyles = `
.error-notification {
    position: fixed;
    top: 20px;
    right: 20px;
    background: #dc3545;
    color: white;
    padding: 1rem;
    border-radius: 4px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    z-index: 1001;
    display: none;
    max-width: 300px;
}
`;

// Add error styles to page
const styleSheet = document.createElement('style');
styleSheet.textContent = errorStyles;
document.head.appendChild(styleSheet);