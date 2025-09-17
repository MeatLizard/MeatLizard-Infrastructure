/**
 * Admin Video Dashboard JavaScript
 */

class AdminVideoDashboard {
    constructor() {
        this.currentPage = 1;
        this.perPage = 50;
        this.selectedVideos = new Set();
        this.filters = {
            status: '',
            visibility: '',
            creator: '',
            search: '',
            sortBy: 'created_at',
            sortOrder: 'desc'
        };
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadDashboardStats();
        this.loadVideosList();
        this.loadStorageReport();
        this.loadTranscodingStatus();
        this.loadCleanupRecommendations();
    }
    
    bindEvents() {
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.refreshAll();
        });
        
        // Filter controls
        document.getElementById('status-filter').addEventListener('change', (e) => {
            this.filters.status = e.target.value;
            this.currentPage = 1;
            this.loadVideosList();
        });
        
        document.getElementById('visibility-filter').addEventListener('change', (e) => {
            this.filters.visibility = e.target.value;
            this.currentPage = 1;
            this.loadVideosList();
        });
        
        document.getElementById('creator-filter').addEventListener('input', 
            this.debounce((e) => {
                this.filters.creator = e.target.value;
                this.currentPage = 1;
                this.loadVideosList();
            }, 500)
        );
        
        document.getElementById('search-filter').addEventListener('input', 
            this.debounce((e) => {
                this.filters.search = e.target.value;
                this.currentPage = 1;
                this.loadVideosList();
            }, 500)
        );
        
        document.getElementById('sort-by').addEventListener('change', (e) => {
            this.filters.sortBy = e.target.value;
            this.loadVideosList();
        });
        
        document.getElementById('sort-order').addEventListener('change', (e) => {
            this.filters.sortOrder = e.target.value;
            this.loadVideosList();
        });
        
        // Select all checkbox
        document.getElementById('select-all-checkbox').addEventListener('change', (e) => {
            this.toggleSelectAll(e.target.checked);
        });
        
        // Bulk actions
        document.getElementById('bulk-visibility-btn').addEventListener('click', () => {
            this.bulkUpdateVisibility();
        });
        
        document.getElementById('bulk-delete-btn').addEventListener('click', () => {
            this.bulkDeleteVideos();
        });
        
        document.getElementById('clear-selection-btn').addEventListener('click', () => {
            this.clearSelection();
        });
        
        // Report tabs
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchReportTab(e.target.dataset.tab);
            });
        });
        
        // Cleanup actions
        document.getElementById('cleanup-deleted-btn').addEventListener('click', () => {
            this.cleanupDeletedVideos();
        });
        
        document.getElementById('cleanup-failed-jobs-btn').addEventListener('click', () => {
            this.cleanupFailedJobs();
        });
        
        // Modal close events
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.closeModal(e.target.closest('.modal'));
            });
        });
        
        // Click outside modal to close
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal);
                }
            });
        });
    }
    
    async loadDashboardStats() {
        try {
            const response = await fetch('/admin/videos/dashboard/stats');
            const stats = await response.json();
            
            this.updateDashboardStats(stats);
        } catch (error) {
            console.error('Error loading dashboard stats:', error);
            this.showError('Failed to load dashboard statistics');
        }
    }
    
    updateDashboardStats(stats) {
        // Total videos
        const totalVideos = Object.values(stats.video_stats).reduce((sum, count) => sum + count, 0);
        document.getElementById('total-videos').textContent = totalVideos.toLocaleString();
        
        // Video status breakdown
        const statusBreakdown = document.getElementById('video-status-breakdown');
        statusBreakdown.innerHTML = '';
        Object.entries(stats.video_stats).forEach(([status, count]) => {
            const span = document.createElement('span');
            span.textContent = `${status}: ${count}`;
            statusBreakdown.appendChild(span);
        });
        
        // Storage usage
        const totalStorage = stats.storage.total_original_gb + stats.storage.total_transcoded_gb;
        document.getElementById('total-storage').textContent = `${totalStorage.toFixed(2)} GB`;
        document.getElementById('original-storage').textContent = `${stats.storage.total_original_gb} GB`;
        document.getElementById('transcoded-storage').textContent = `${stats.storage.total_transcoded_gb} GB`;
        
        // Transcoding queue
        const totalJobs = Object.values(stats.transcoding_stats).reduce((sum, count) => sum + count, 0);
        document.getElementById('queue-status').textContent = totalJobs.toLocaleString();
        
        const transcodingBreakdown = document.getElementById('transcoding-status-breakdown');
        transcodingBreakdown.innerHTML = '';
        Object.entries(stats.transcoding_stats).forEach(([status, count]) => {
            const span = document.createElement('span');
            span.textContent = `${status}: ${count}`;
            transcodingBreakdown.appendChild(span);
        });
        
        // Recent activity
        document.getElementById('recent-uploads').textContent = stats.recent_activity.uploads_24h;
        document.getElementById('recent-views').textContent = stats.recent_activity.views_24h;
        document.getElementById('failed-jobs').textContent = stats.recent_activity.failed_jobs;
    }
    
    async loadVideosList() {
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: this.perPage,
                sort_by: this.filters.sortBy,
                sort_order: this.filters.sortOrder
            });
            
            if (this.filters.status) params.append('status', this.filters.status);
            if (this.filters.visibility) params.append('visibility', this.filters.visibility);
            if (this.filters.creator) params.append('creator', this.filters.creator);
            if (this.filters.search) params.append('search', this.filters.search);
            
            const response = await fetch(`/admin/videos/list?${params}`);
            const data = await response.json();
            
            this.updateVideosTable(data.videos);
            this.updatePagination(data.pagination);
        } catch (error) {
            console.error('Error loading videos list:', error);
            this.showError('Failed to load videos list');
        }
    }
    
    updateVideosTable(videos) {
        const tbody = document.getElementById('videos-table-body');
        tbody.innerHTML = '';
        
        videos.forEach(video => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <input type="checkbox" class="video-checkbox" value="${video.id}" 
                           ${this.selectedVideos.has(video.id) ? 'checked' : ''}>
                </td>
                <td>
                    <div class="video-title">
                        <strong>${this.escapeHtml(video.title)}</strong>
                        <div class="video-id">${video.id}</div>
                    </div>
                </td>
                <td>
                    <div class="creator-info">
                        <div>${this.escapeHtml(video.creator.display_label)}</div>
                        <div class="creator-email">${this.escapeHtml(video.creator.email || '')}</div>
                    </div>
                </td>
                <td>
                    <span class="status-badge status-${video.status}">${video.status}</span>
                </td>
                <td>
                    <span class="visibility-badge visibility-${video.visibility}">${video.visibility}</span>
                </td>
                <td>${video.file_size_mb} MB</td>
                <td>${this.formatDuration(video.duration_seconds)}</td>
                <td>
                    <div class="transcoding-summary">
                        <span class="success">${video.transcoding_summary.completed_jobs}</span> /
                        <span class="warning">${video.transcoding_summary.processing_jobs}</span> /
                        <span class="danger">${video.transcoding_summary.failed_jobs}</span>
                        (${video.transcoding_summary.total_jobs} total)
                    </div>
                </td>
                <td>${new Date(video.created_at).toLocaleDateString()}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="adminDashboard.viewVideoDetails('${video.id}')">
                        Details
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
        
        // Bind checkbox events
        document.querySelectorAll('.video-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.toggleVideoSelection(e.target.value, e.target.checked);
            });
        });
    }
    
    updatePagination(pagination) {
        document.getElementById('pagination-info').textContent = 
            `Showing ${((pagination.page - 1) * pagination.per_page) + 1}-${Math.min(pagination.page * pagination.per_page, pagination.total_count)} of ${pagination.total_count} videos`;
        
        // Update pagination controls
        const prevBtn = document.getElementById('prev-page-btn');
        const nextBtn = document.getElementById('next-page-btn');
        
        prevBtn.disabled = pagination.page <= 1;
        nextBtn.disabled = pagination.page >= pagination.total_pages;
        
        prevBtn.onclick = () => {
            if (pagination.page > 1) {
                this.currentPage = pagination.page - 1;
                this.loadVideosList();
            }
        };
        
        nextBtn.onclick = () => {
            if (pagination.page < pagination.total_pages) {
                this.currentPage = pagination.page + 1;
                this.loadVideosList();
            }
        };
        
        // Update page numbers
        const pageNumbers = document.getElementById('page-numbers');
        pageNumbers.innerHTML = '';
        
        const startPage = Math.max(1, pagination.page - 2);
        const endPage = Math.min(pagination.total_pages, pagination.page + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.className = `page-number ${i === pagination.page ? 'active' : ''}`;
            pageBtn.textContent = i;
            pageBtn.onclick = () => {
                this.currentPage = i;
                this.loadVideosList();
            };
            pageNumbers.appendChild(pageBtn);
        }
    }
    
    toggleVideoSelection(videoId, selected) {
        if (selected) {
            this.selectedVideos.add(videoId);
        } else {
            this.selectedVideos.delete(videoId);
        }
        
        this.updateBulkActionsPanel();
    }
    
    toggleSelectAll(selectAll) {
        const checkboxes = document.querySelectorAll('.video-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = selectAll;
            this.toggleVideoSelection(checkbox.value, selectAll);
        });
    }
    
    updateBulkActionsPanel() {
        const panel = document.getElementById('bulk-actions-panel');
        const button = document.getElementById('bulk-actions-btn');
        const count = this.selectedVideos.size;
        
        if (count > 0) {
            panel.style.display = 'block';
            button.disabled = false;
            document.getElementById('selected-count').textContent = `${count} video${count !== 1 ? 's' : ''} selected`;
        } else {
            panel.style.display = 'none';
            button.disabled = true;
        }
    }
    
    clearSelection() {
        this.selectedVideos.clear();
        document.querySelectorAll('.video-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        document.getElementById('select-all-checkbox').checked = false;
        this.updateBulkActionsPanel();
    }
    
    async bulkUpdateVisibility() {
        const visibility = document.getElementById('bulk-visibility-select').value;
        if (!visibility) {
            this.showError('Please select a visibility option');
            return;
        }
        
        const videoIds = Array.from(this.selectedVideos);
        if (videoIds.length === 0) {
            this.showError('No videos selected');
            return;
        }
        
        const confirmed = await this.showConfirmation(
            `Are you sure you want to change visibility to "${visibility}" for ${videoIds.length} video(s)?`
        );
        
        if (!confirmed) return;
        
        try {
            const response = await fetch('/admin/videos/bulk/update-visibility', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    video_ids: videoIds,
                    visibility: visibility
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess(`Updated visibility for ${result.updated_count} videos`);
                this.clearSelection();
                this.loadVideosList();
            } else {
                this.showError(result.detail || 'Failed to update visibility');
            }
        } catch (error) {
            console.error('Error updating visibility:', error);
            this.showError('Failed to update visibility');
        }
    }
    
    async bulkDeleteVideos() {
        const videoIds = Array.from(this.selectedVideos);
        if (videoIds.length === 0) {
            this.showError('No videos selected');
            return;
        }
        
        const confirmed = await this.showConfirmation(
            `Are you sure you want to delete ${videoIds.length} video(s)? This action cannot be undone.`
        );
        
        if (!confirmed) return;
        
        try {
            const response = await fetch('/admin/videos/bulk/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    video_ids: videoIds
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess(`Deleted ${result.deleted_count} videos`);
                this.clearSelection();
                this.loadVideosList();
                this.loadDashboardStats();
            } else {
                this.showError(result.detail || 'Failed to delete videos');
            }
        } catch (error) {
            console.error('Error deleting videos:', error);
            this.showError('Failed to delete videos');
        }
    }
    
    async viewVideoDetails(videoId) {
        try {
            const response = await fetch(`/admin/videos/${videoId}/details`);
            const video = await response.json();
            
            if (response.ok) {
                this.showVideoDetailsModal(video);
            } else {
                this.showError(video.detail || 'Failed to load video details');
            }
        } catch (error) {
            console.error('Error loading video details:', error);
            this.showError('Failed to load video details');
        }
    }
    
    showVideoDetailsModal(video) {
        const modal = document.getElementById('video-details-modal');
        const content = document.getElementById('video-details-content');
        
        content.innerHTML = `
            <div class="video-detail-section">
                <h3>Basic Information</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Title</div>
                        <div class="detail-value">${this.escapeHtml(video.title)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Creator</div>
                        <div class="detail-value">${this.escapeHtml(video.creator.display_label)} (${this.escapeHtml(video.creator.email)})</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Status</div>
                        <div class="detail-value">
                            <span class="status-badge status-${video.status}">${video.status}</span>
                        </div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Visibility</div>
                        <div class="detail-value">
                            <span class="visibility-badge visibility-${video.visibility}">${video.visibility}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="video-detail-section">
                <h3>File Information</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Original Filename</div>
                        <div class="detail-value">${this.escapeHtml(video.file_info.original_filename)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">File Size</div>
                        <div class="detail-value">${video.file_info.file_size_mb} MB</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Duration</div>
                        <div class="detail-value">${this.formatDuration(video.file_info.duration_seconds)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Resolution</div>
                        <div class="detail-value">${video.file_info.source_resolution || 'Unknown'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Framerate</div>
                        <div class="detail-value">${video.file_info.source_framerate || 'Unknown'} fps</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Codec</div>
                        <div class="detail-value">${video.file_info.source_codec || 'Unknown'}</div>
                    </div>
                </div>
            </div>
            
            <div class="video-detail-section">
                <h3>Statistics</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Total Views</div>
                        <div class="detail-value">${video.statistics.total_views}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Watch Time</div>
                        <div class="detail-value">${video.statistics.total_watch_time_hours} hours</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Avg Completion</div>
                        <div class="detail-value">${video.statistics.average_completion_percent}%</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Likes</div>
                        <div class="detail-value">${video.statistics.likes}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Dislikes</div>
                        <div class="detail-value">${video.statistics.dislikes}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Comments</div>
                        <div class="detail-value">${video.statistics.comments}</div>
                    </div>
                </div>
            </div>
            
            <div class="video-detail-section">
                <h3>Transcoding Jobs</h3>
                ${video.transcoding_jobs.map(job => `
                    <div class="transcoding-job">
                        <div class="job-header">
                            <span class="job-quality">${job.quality_preset}</span>
                            <span class="status-badge status-${job.status}">${job.status}</span>
                            ${job.status === 'failed' ? `
                                <button class="btn btn-sm btn-warning" onclick="adminDashboard.retryTranscodingJob('${job.id}')">
                                    Retry
                                </button>
                            ` : ''}
                        </div>
                        <div class="job-details">
                            <div>Resolution: ${job.target_resolution}</div>
                            <div>Framerate: ${job.target_framerate} fps</div>
                            <div>Progress: ${job.progress_percent}%</div>
                            ${job.output_file_size_mb ? `<div>Output Size: ${job.output_file_size_mb} MB</div>` : ''}
                            <div>Created: ${new Date(job.created_at).toLocaleString()}</div>
                            ${job.completed_at ? `<div>Completed: ${new Date(job.completed_at).toLocaleString()}</div>` : ''}
                        </div>
                        ${job.error_message ? `
                            <div class="error-message">${this.escapeHtml(job.error_message)}</div>
                        ` : ''}
                    </div>
                `).join('')}
            </div>
        `;
        
        modal.style.display = 'block';
    }
    
    async retryTranscodingJob(jobId) {
        try {
            const response = await fetch('/admin/videos/transcoding/retry', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    job_id: jobId
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess('Transcoding job queued for retry');
                this.closeModal(document.getElementById('video-details-modal'));
                this.loadVideosList();
                this.loadDashboardStats();
            } else {
                this.showError(result.detail || 'Failed to retry transcoding job');
            }
        } catch (error) {
            console.error('Error retrying transcoding job:', error);
            this.showError('Failed to retry transcoding job');
        }
    }
    
    async loadStorageReport() {
        try {
            const response = await fetch('/admin/videos/storage/report');
            const report = await response.json();
            
            this.updateStorageReport(report);
        } catch (error) {
            console.error('Error loading storage report:', error);
        }
    }
    
    updateStorageReport(report) {
        // Update creator storage table
        const creatorTable = document.getElementById('creator-storage-table');
        creatorTable.innerHTML = '';
        report.storage_by_creator.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${this.escapeHtml(item.creator)} (${this.escapeHtml(item.email)})</td>
                <td>${item.video_count}</td>
                <td>${item.size_gb}</td>
            `;
            creatorTable.appendChild(row);
        });
        
        // Update quality storage table
        const qualityTable = document.getElementById('quality-storage-table');
        qualityTable.innerHTML = '';
        report.storage_by_quality.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.quality_preset}</td>
                <td>${item.job_count}</td>
                <td>${item.size_gb}</td>
            `;
            qualityTable.appendChild(row);
        });
    }
    
    async loadTranscodingStatus() {
        try {
            const response = await fetch('/admin/videos/transcoding/queue-status');
            const status = await response.json();
            
            this.updateTranscodingStatus(status);
        } catch (error) {
            console.error('Error loading transcoding status:', error);
        }
    }
    
    updateTranscodingStatus(status) {
        // Update performance metrics
        document.getElementById('completed-jobs-24h').textContent = status.recent_performance.completed_24h;
        document.getElementById('avg-duration').textContent = `${status.recent_performance.avg_duration_minutes} min`;
        
        // Update common errors
        const errorList = document.getElementById('error-list');
        errorList.innerHTML = '';
        status.common_errors.forEach(error => {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-item';
            errorDiv.innerHTML = `
                <div><strong>Count:</strong> ${error.count}</div>
                <div class="error-message">${this.escapeHtml(error.error_message || 'Unknown error')}</div>
            `;
            errorList.appendChild(errorDiv);
        });
    }
    
    async loadCleanupRecommendations() {
        try {
            const response = await fetch('/admin/videos/cleanup/recommendations');
            const recommendations = await response.json();
            
            this.updateCleanupRecommendations(recommendations);
        } catch (error) {
            console.error('Error loading cleanup recommendations:', error);
        }
    }
    
    updateCleanupRecommendations(recommendations) {
        document.getElementById('deleted-videos-count').textContent = recommendations.deleted_videos_to_cleanup.count;
        document.getElementById('deleted-videos-storage').textContent = recommendations.deleted_videos_to_cleanup.estimated_storage_gb.toFixed(2);
        document.getElementById('old-failed-jobs-count').textContent = recommendations.old_failed_jobs_to_remove.count;
    }
    
    switchReportTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Update tab content
        document.querySelectorAll('.report-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.getElementById(`storage-${tabName}`).classList.add('active');
    }
    
    refreshAll() {
        this.loadDashboardStats();
        this.loadVideosList();
        this.loadStorageReport();
        this.loadTranscodingStatus();
        this.loadCleanupRecommendations();
    }
    
    closeModal(modal) {
        modal.style.display = 'none';
    }
    
    showConfirmation(message) {
        return new Promise((resolve) => {
            const modal = document.getElementById('confirmation-modal');
            const messageEl = document.getElementById('confirmation-message');
            const confirmBtn = document.getElementById('confirm-action-btn');
            
            messageEl.textContent = message;
            modal.style.display = 'block';
            
            const handleConfirm = () => {
                modal.style.display = 'none';
                confirmBtn.removeEventListener('click', handleConfirm);
                resolve(true);
            };
            
            const handleCancel = () => {
                modal.style.display = 'none';
                confirmBtn.removeEventListener('click', handleConfirm);
                resolve(false);
            };
            
            confirmBtn.addEventListener('click', handleConfirm);
            modal.querySelector('.modal-close').addEventListener('click', handleCancel, { once: true });
        });
    }
    
    showSuccess(message) {
        // Simple success notification - could be enhanced with a proper notification system
        alert(`Success: ${message}`);
    }
    
    showError(message) {
        // Simple error notification - could be enhanced with a proper notification system
        alert(`Error: ${message}`);
    }
    
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Initialize the dashboard when the page loads
let adminDashboard;
document.addEventListener('DOMContentLoaded', () => {
    adminDashboard = new AdminVideoDashboard();
});