/**
 * Viewing History Management
 */

class ViewingHistoryManager {
    constructor() {
        this.currentPage = 1;
        this.totalPages = 1;
        this.isLoading = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadViewingHistory();
        this.loadContinueWatching();
        this.loadRecommendations();
    }
    
    setupEventListeners() {
        // Clear history button
        document.getElementById('clear-history-btn')?.addEventListener('click', () => {
            this.clearHistory();
        });
        
        // Privacy settings button
        document.getElementById('privacy-settings-btn')?.addEventListener('click', () => {
            this.showPrivacySettings();
        });
        
        // Pagination buttons
        document.getElementById('prev-page')?.addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.loadViewingHistory(this.currentPage - 1);
            }
        });
        
        document.getElementById('next-page')?.addEventListener('click', () => {
            if (this.currentPage < this.totalPages) {
                this.loadViewingHistory(this.currentPage + 1);
            }
        });
        
        // Retry button
        document.getElementById('retry-btn')?.addEventListener('click', () => {
            this.loadViewingHistory();
        });
        
        // Privacy modal
        document.getElementById('close-modal')?.addEventListener('click', () => {
            this.hidePrivacySettings();
        });
        
        document.getElementById('cancel-privacy')?.addEventListener('click', () => {
            this.hidePrivacySettings();
        });
        
        document.getElementById('save-privacy')?.addEventListener('click', () => {
            this.savePrivacySettings();
        });
        
        // Close modal when clicking outside
        document.getElementById('privacy-modal')?.addEventListener('click', (e) => {
            if (e.target.id === 'privacy-modal') {
                this.hidePrivacySettings();
            }
        });
    }
    
    async loadViewingHistory(page = 1) {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();
        
        try {
            const response = await fetch(`/api/users/me/viewing-history?page=${page}&limit=20`);
            
            if (response.ok) {
                const data = await response.json();
                this.renderHistory(data.history);
                this.updatePagination(data.pagination);
                this.currentPage = page;
                this.totalPages = data.pagination.pages;
            } else if (response.status === 401) {
                this.showError('Please sign in to view your history');
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to load viewing history:', error);
            this.showError('Failed to load viewing history');
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }
    
    async loadContinueWatching() {
        try {
            const response = await fetch('/api/users/me/continue-watching?limit=5');
            
            if (response.ok) {
                const data = await response.json();
                if (data.continue_watching.length > 0) {
                    this.renderContinueWatching(data.continue_watching);
                }
            }
        } catch (error) {
            console.warn('Failed to load continue watching:', error);
        }
    }
    
    async loadRecommendations() {
        try {
            const response = await fetch('/api/users/me/recommendations?limit=10');
            
            if (response.ok) {
                const data = await response.json();
                if (data.recommendations.length > 0) {
                    this.renderRecommendations(data.recommendations);
                }
            }
        } catch (error) {
            console.warn('Failed to load recommendations:', error);
        }
    }
    
    renderHistory(history) {
        const historyList = document.getElementById('history-list');
        const emptyState = document.getElementById('empty-state');
        
        if (history.length === 0) {
            historyList.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }
        
        emptyState.style.display = 'none';
        historyList.style.display = 'block';
        
        historyList.innerHTML = '';
        
        history.forEach(item => {
            const historyItem = this.createHistoryItem(item);
            historyList.appendChild(historyItem);
        });
    }
    
    createHistoryItem(item) {
        const div = document.createElement('div');
        div.className = 'history-item';
        div.dataset.videoId = item.video_id;
        
        const watchedDate = new Date(item.watched_at);
        const formattedDate = this.formatDate(watchedDate);
        const duration = this.formatDuration(item.duration_seconds);
        const resumePosition = this.formatDuration(item.watch_progress.current_position_seconds);
        
        div.innerHTML = `
            <div class="video-thumbnail">
                ${item.thumbnail_url ? 
                    `<img src="${item.thumbnail_url}" alt="${this.escapeHtml(item.title)}" loading="lazy">` :
                    `<div class="thumbnail-placeholder"><span>📹</span></div>`
                }
                
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${item.watch_progress.completion_percentage}%"></div>
                </div>
                
                <div class="video-duration">${duration}</div>
            </div>
            
            <div class="video-info">
                <h3 class="video-title">
                    <a href="/video-player?video_id=${item.video_id}">${this.escapeHtml(item.title)}</a>
                </h3>
                
                <p class="video-description">
                    ${this.escapeHtml(item.description ? item.description.substring(0, 150) : '')}${item.description && item.description.length > 150 ? '...' : ''}
                </p>
                
                <div class="video-meta">
                    <span class="creator-name">By ${this.escapeHtml(item.creator_name)}</span>
                    <span class="watch-time">• Watched ${formattedDate}</span>
                    
                    ${item.can_resume ? 
                        `<span class="resume-info">• Resume at ${resumePosition}</span>` :
                        item.watch_progress.completion_percentage >= 95 ? 
                            `<span class="completed-info">• Completed</span>` : ''
                    }
                </div>
                
                <div class="video-stats">
                    <div class="stat">
                        <span class="stat-label">Watch Time:</span>
                        <span class="stat-value">${this.formatDuration(item.watch_progress.total_watch_time_seconds)}</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Progress:</span>
                        <span class="stat-value">${item.watch_progress.completion_percentage}%</span>
                    </div>
                </div>
            </div>
            
            <div class="video-actions">
                <a href="/video-player?video_id=${item.video_id}" class="action-button primary">
                    ${item.can_resume ? 'Resume' : 'Watch'}
                </a>
                
                <button class="action-button secondary" onclick="viewingHistory.removeFromHistory('${item.video_id}')">
                    Remove
                </button>
            </div>
        `;
        
        return div;
    }
    
    renderContinueWatching(continueWatching) {
        const section = document.getElementById('continue-watching-section');
        const list = document.getElementById('continue-watching-list');
        
        section.style.display = 'block';
        list.innerHTML = '';
        
        continueWatching.forEach(item => {
            const div = document.createElement('div');
            div.className = 'continue-item';
            
            const resumePosition = this.formatDuration(item.resume_position_seconds);
            const remaining = this.formatDuration(item.remaining_seconds);
            
            div.innerHTML = `
                <div class="continue-thumbnail">
                    ${item.thumbnail_url ? 
                        `<img src="${item.thumbnail_url}" alt="${this.escapeHtml(item.title)}" loading="lazy">` :
                        `<div class="thumbnail-placeholder"><span>📹</span></div>`
                    }
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${item.completion_percentage}%"></div>
                    </div>
                    <div class="resume-overlay">
                        <span class="resume-text">Resume at ${resumePosition}</span>
                    </div>
                </div>
                
                <div class="continue-info">
                    <h4 class="continue-title">
                        <a href="/video-player?video_id=${item.video_id}">${this.escapeHtml(item.title)}</a>
                    </h4>
                    <p class="continue-creator">By ${this.escapeHtml(item.creator_name)}</p>
                    <p class="continue-remaining">${remaining} remaining</p>
                </div>
            `;
            
            list.appendChild(div);
        });
    }
    
    renderRecommendations(recommendations) {
        const section = document.getElementById('recommendations-section');
        const list = document.getElementById('recommendations-list');
        
        section.style.display = 'block';
        list.innerHTML = '';
        
        recommendations.forEach(item => {
            const div = document.createElement('div');
            div.className = 'recommendation-item';
            
            const duration = this.formatDuration(item.duration_seconds);
            
            div.innerHTML = `
                <div class="recommendation-thumbnail">
                    ${item.thumbnail_url ? 
                        `<img src="${item.thumbnail_url}" alt="${this.escapeHtml(item.title)}" loading="lazy">` :
                        `<div class="thumbnail-placeholder"><span>📹</span></div>`
                    }
                    <div class="video-duration">${duration}</div>
                </div>
                
                <div class="recommendation-info">
                    <h4 class="recommendation-title">
                        <a href="/video-player?video_id=${item.video_id}">${this.escapeHtml(item.title)}</a>
                    </h4>
                    <p class="recommendation-creator">By ${this.escapeHtml(item.creator_name)}</p>
                    <p class="recommendation-reason">${item.recommendation_reason}</p>
                </div>
            `;
            
            list.appendChild(div);
        });
    }
    
    updatePagination(pagination) {
        const paginationDiv = document.getElementById('pagination');
        const prevButton = document.getElementById('prev-page');
        const nextButton = document.getElementById('next-page');
        const pageInfo = document.getElementById('page-info');
        
        if (pagination.pages > 1) {
            paginationDiv.style.display = 'flex';
            
            prevButton.disabled = pagination.page <= 1;
            nextButton.disabled = pagination.page >= pagination.pages;
            
            pageInfo.textContent = `Page ${pagination.page} of ${pagination.pages}`;
        } else {
            paginationDiv.style.display = 'none';
        }
    }
    
    async removeFromHistory(videoId) {
        if (!confirm('Remove this video from your viewing history?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/users/me/viewing-history/${videoId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                // Remove the item from the UI
                const historyItem = document.querySelector(`[data-video-id="${videoId}"]`);
                if (historyItem) {
                    historyItem.remove();
                }
                
                // Check if list is now empty
                const historyList = document.getElementById('history-list');
                if (historyList.children.length === 0) {
                    this.loadViewingHistory(this.currentPage);
                }
                
                this.showMessage('Video removed from history', 'success');
            } else if (response.status === 401) {
                this.showMessage('Please sign in to manage your history', 'error');
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to remove from history:', error);
            this.showMessage('Failed to remove video from history', 'error');
        }
    }
    
    async clearHistory() {
        if (!confirm('Are you sure you want to clear your entire viewing history? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch('/api/users/me/viewing-history', {
                method: 'DELETE'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.loadViewingHistory(1);
                this.showMessage(`Cleared ${data.cleared_count} items from history`, 'success');
            } else if (response.status === 401) {
                this.showMessage('Please sign in to manage your history', 'error');
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to clear history:', error);
            this.showMessage('Failed to clear viewing history', 'error');
        }
    }
    
    async showPrivacySettings() {
        try {
            // Load current privacy settings
            const response = await fetch('/api/users/me/history-privacy');
            
            if (response.ok) {
                const data = await response.json();
                document.getElementById('history-public-checkbox').checked = data.is_history_public;
            }
        } catch (error) {
            console.warn('Failed to load privacy settings:', error);
        }
        
        document.getElementById('privacy-modal').style.display = 'flex';
    }
    
    hidePrivacySettings() {
        document.getElementById('privacy-modal').style.display = 'none';
    }
    
    async savePrivacySettings() {
        const isPublic = document.getElementById('history-public-checkbox').checked;
        
        try {
            const response = await fetch('/api/users/me/history-privacy', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    is_history_public: isPublic
                })
            });
            
            if (response.ok) {
                this.hidePrivacySettings();
                this.showMessage('Privacy settings updated', 'success');
            } else if (response.status === 401) {
                this.showMessage('Please sign in to update settings', 'error');
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to save privacy settings:', error);
            this.showMessage('Failed to update privacy settings', 'error');
        }
    }
    
    showLoading() {
        document.getElementById('loading-state').style.display = 'block';
        document.getElementById('error-state').style.display = 'none';
        document.getElementById('empty-state').style.display = 'none';
        document.getElementById('history-list').style.display = 'none';
    }
    
    hideLoading() {
        document.getElementById('loading-state').style.display = 'none';
    }
    
    showError(message) {
        document.getElementById('error-state').style.display = 'block';
        document.getElementById('error-state').querySelector('.error-text').textContent = message;
        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('empty-state').style.display = 'none';
        document.getElementById('history-list').style.display = 'none';
    }
    
    showMessage(message, type = 'info') {
        // Create a temporary message element
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = message;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        
        if (type === 'success') {
            messageDiv.style.backgroundColor = '#4caf50';
        } else if (type === 'error') {
            messageDiv.style.backgroundColor = '#f44336';
        } else {
            messageDiv.style.backgroundColor = '#2196f3';
        }
        
        document.body.appendChild(messageDiv);
        
        setTimeout(() => {
            messageDiv.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                document.body.removeChild(messageDiv);
            }, 300);
        }, 3000);
    }
    
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    formatDate(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return 'Today';
        } else if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else {
            return date.toLocaleDateString();
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize viewing history manager
const viewingHistory = new ViewingHistoryManager();

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);