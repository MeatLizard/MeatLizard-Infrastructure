/**
 * Moderation Dashboard JavaScript
 * Handles content moderation interface and actions
 */

class ModerationDashboard {
    constructor() {
        this.currentQueue = [];
        this.selectedItem = null;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadModerationQueue();
        this.loadDashboardStats();
    }
    
    bindEvents() {
        // Queue filters
        document.getElementById('content-type-filter').addEventListener('change', () => {
            this.loadModerationQueue();
        });
        
        document.getElementById('priority-filter').addEventListener('change', () => {
            this.loadModerationQueue();
        });
        
        document.getElementById('refresh-queue').addEventListener('click', () => {
            this.loadModerationQueue();
        });
        
        // Moderation actions
        document.getElementById('moderation-action').addEventListener('change', (e) => {
            this.updateActionForm(e.target.value);
        });
        
        document.getElementById('apply-action').addEventListener('click', () => {
            this.applyModerationAction();
        });
        
        // Scan functionality
        document.getElementById('start-scan').addEventListener('click', () => {
            this.startContentScan();
        });
        
        // Bulk actions
        document.getElementById('apply-bulk-action').addEventListener('click', () => {
            this.applyBulkAction();
        });
        
        // Report submission
        document.getElementById('submit-report').addEventListener('click', () => {
            this.submitContentReport();
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
    
    async loadModerationQueue() {
        const contentType = document.getElementById('content-type-filter').value;
        const priority = document.getElementById('priority-filter').value;
        
        try {
            const params = new URLSearchParams();
            if (contentType) params.append('content_type', contentType);
            if (priority) params.append('priority', priority);
            params.append('limit', '50');
            
            const response = await fetch(`/api/moderation/queue?${params}`);
            const data = await response.json();
            
            if (response.ok) {
                this.currentQueue = data.items;
                this.renderModerationQueue();
            } else {
                this.showNotification('Failed to load moderation queue', 'error');
            }
        } catch (error) {
            console.error('Error loading moderation queue:', error);
            this.showNotification('Error loading moderation queue', 'error');
        }
    }
    
    renderModerationQueue() {
        const container = document.getElementById('moderation-queue');
        
        if (this.currentQueue.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="icon-check-circle"></i>
                    <h3>No pending items</h3>
                    <p>All reports have been reviewed!</p>
                </div>
            `;
            return;
        }
        
        const queueHtml = this.currentQueue.map(item => `
            <div class="queue-item priority-${item.priority}" onclick="moderationDashboard.openModerationModal('${item.report_id}')">
                <div class="item-header">
                    <div class="item-type ${item.content_type}">${item.content_type}</div>
                    <div class="item-priority priority-${item.priority}">${item.priority}</div>
                </div>
                <div class="item-content">
                    <div class="item-title">${item.content_details?.title || 'Content ID: ' + item.content_id}</div>
                    <div class="item-description">${item.description || 'No description provided'}</div>
                </div>
                <div class="item-meta">
                    <span class="item-reason">${this.formatReason(item.reason)}</span>
                    <span class="item-date">${this.formatDate(item.created_at)}</span>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = queueHtml;
    }
    
    async openModerationModal(reportId) {
        const item = this.currentQueue.find(i => i.report_id === reportId);
        if (!item) return;
        
        this.selectedItem = item;
        
        // Populate content preview
        this.renderContentPreview(item);
        
        // Populate report details
        this.renderReportDetails(item);
        
        // Populate scan results if available
        this.renderScanResults(item.scan_results);
        
        // Reset form
        this.resetModerationForm();
        
        // Show modal
        document.getElementById('moderation-modal').style.display = 'block';
    }
    
    renderContentPreview(item) {
        const container = document.getElementById('content-preview');
        const content = item.content_details;
        
        let previewHtml = `<h4>Content Preview</h4>`;
        
        if (item.content_type === 'video') {
            previewHtml += `
                <div class="content-title">${content?.title || 'Untitled Video'}</div>
                <div class="content-description">${content?.description || 'No description'}</div>
                <div class="content-meta">
                    <span>Duration: ${content?.duration || 'Unknown'}</span>
                    <span>Created: ${content?.created_at ? this.formatDate(content.created_at) : 'Unknown'}</span>
                </div>
            `;
        } else if (item.content_type === 'comment') {
            previewHtml += `
                <div class="content-title">Comment</div>
                <div class="content-description">${content?.content || 'Comment content not available'}</div>
            `;
        } else {
            previewHtml += `
                <div class="content-title">${item.content_type.charAt(0).toUpperCase() + item.content_type.slice(1)}</div>
                <div class="content-description">Content ID: ${item.content_id}</div>
            `;
        }
        
        container.innerHTML = previewHtml;
    }
    
    renderReportDetails(item) {
        const container = document.getElementById('report-details');
        
        const reportHtml = `
            <h4>Report Details</h4>
            <div class="report-meta">
                <div class="report-meta-item">
                    <span class="report-meta-label">Reporter:</span> ${item.reporter_id}
                </div>
                <div class="report-meta-item">
                    <span class="report-meta-label">Reason:</span> ${this.formatReason(item.reason)}
                </div>
                <div class="report-meta-item">
                    <span class="report-meta-label">Submitted:</span> ${this.formatDate(item.created_at)}
                </div>
            </div>
            ${item.description ? `<div class="report-description">"${item.description}"</div>` : ''}
        `;
        
        container.innerHTML = reportHtml;
    }
    
    renderScanResults(scanResults) {
        const container = document.getElementById('scan-results');
        
        if (!scanResults) {
            container.innerHTML = '<h4>Automated Scan</h4><p>No automated scan results available.</p>';
            return;
        }
        
        const riskClass = scanResults.overall_risk || 'low';
        container.className = `scan-results ${riskClass}-risk`;
        
        let scanHtml = `
            <h4>Automated Scan Results</h4>
            <div class="scan-summary">
                <span class="risk-level ${riskClass}">${riskClass} risk</span>
                <span class="recommended-action">Recommended: ${scanResults.recommended_action || 'Review'}</span>
            </div>
        `;
        
        if (scanResults.flags && scanResults.flags.length > 0) {
            scanHtml += `
                <div class="scan-flags">
                    <strong>Flags:</strong>
                    ${scanResults.flags.map(flag => `<span class="scan-flag">${flag}</span>`).join('')}
                </div>
            `;
        }
        
        container.innerHTML = scanHtml;
    }
    
    resetModerationForm() {
        document.getElementById('moderation-action').value = 'approved';
        document.getElementById('moderation-reason').value = 'inappropriate_content';
        document.getElementById('moderation-notes').value = '';
        document.getElementById('action-duration').value = '';
        this.updateActionForm('approved');
    }
    
    updateActionForm(action) {
        const durationSection = document.getElementById('duration-section');
        
        // Show duration input for temporary actions
        if (['restricted', 'hidden'].includes(action)) {
            durationSection.style.display = 'block';
        } else {
            durationSection.style.display = 'none';
        }
    }
    
    async applyModerationAction() {
        if (!this.selectedItem) return;
        
        const action = document.getElementById('moderation-action').value;
        const reason = document.getElementById('moderation-reason').value;
        const notes = document.getElementById('moderation-notes').value;
        const duration = document.getElementById('action-duration').value;
        
        try {
            const requestBody = {
                report_id: this.selectedItem.report_id,
                action: action,
                reason: reason,
                notes: notes || undefined
            };
            
            const response = await fetch(`/api/moderation/reports/${this.selectedItem.report_id}/resolve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showNotification('Moderation action applied successfully', 'success');
                this.closeModerationModal();
                this.loadModerationQueue(); // Refresh queue
                this.loadDashboardStats(); // Update stats
            } else {
                throw new Error(result.message || 'Failed to apply moderation action');
            }
        } catch (error) {
            console.error('Error applying moderation action:', error);
            this.showNotification('Failed to apply moderation action: ' + error.message, 'error');
        }
    }
    
    async startContentScan() {
        const videoId = document.getElementById('scan-video-id').value.trim();
        const scanMetadata = document.getElementById('scan-metadata').checked;
        const scanVisual = document.getElementById('scan-visual').checked;
        const scanAudio = document.getElementById('scan-audio').checked;
        
        if (!videoId) {
            this.showNotification('Please enter a video ID', 'error');
            return;
        }
        
        try {
            const response = await fetch('/api/moderation/scan/video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    video_id: videoId,
                    scan_metadata: scanMetadata,
                    scan_visual: scanVisual,
                    scan_audio: scanAudio
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.displayScanResults(result);
                this.showNotification('Content scan completed', 'success');
            } else {
                throw new Error(result.message || 'Scan failed');
            }
        } catch (error) {
            console.error('Error scanning content:', error);
            this.showNotification('Failed to scan content: ' + error.message, 'error');
        }
    }
    
    displayScanResults(results) {
        const container = document.getElementById('scan-results-display');
        const resultsContainer = document.getElementById('scan-results-container');
        
        let resultsHtml = `
            <div class="scan-summary">
                <span class="risk-level ${results.overall_risk}">${results.overall_risk} risk</span>
                <span class="recommended-action">Recommended: ${results.recommended_action}</span>
            </div>
        `;
        
        if (results.flags && results.flags.length > 0) {
            resultsHtml += `
                <div class="scan-flags">
                    <strong>Issues Found:</strong>
                    ${results.flags.map(flag => `<span class="scan-flag">${flag}</span>`).join('')}
                </div>
            `;
        }
        
        if (results.metadata_scan) {
            resultsHtml += `
                <div class="scan-section">
                    <h5>Metadata Scan</h5>
                    <p>Risk Level: <span class="risk-level ${results.metadata_scan.risk_level}">${results.metadata_scan.risk_level}</span></p>
                </div>
            `;
        }
        
        container.innerHTML = resultsHtml;
        resultsContainer.style.display = 'block';
    }
    
    async applyBulkAction() {
        const contentIds = document.getElementById('bulk-content-ids').value
            .split('\n')
            .map(id => id.trim())
            .filter(id => id.length > 0);
        
        const action = document.getElementById('bulk-action').value;
        const reason = document.getElementById('bulk-reason').value;
        const notes = document.getElementById('bulk-notes').value;
        
        if (contentIds.length === 0) {
            this.showNotification('Please enter at least one content ID', 'error');
            return;
        }
        
        try {
            const response = await fetch('/api/moderation/bulk-action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content_ids: contentIds,
                    action: action,
                    reason: reason,
                    notes: notes || undefined
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showNotification(
                    `Bulk action completed: ${result.successful}/${result.total_processed} successful`,
                    result.failed > 0 ? 'warning' : 'success'
                );
                this.closeBulkActionModal();
                this.loadModerationQueue();
                this.loadDashboardStats();
            } else {
                throw new Error('Bulk action failed');
            }
        } catch (error) {
            console.error('Error applying bulk action:', error);
            this.showNotification('Failed to apply bulk action: ' + error.message, 'error');
        }
    }
    
    async submitContentReport() {
        const contentType = document.getElementById('report-content-type').value;
        const contentId = document.getElementById('report-content-id').value.trim();
        const reason = document.getElementById('report-reason').value;
        const description = document.getElementById('report-description').value.trim();
        const evidenceUrls = document.getElementById('report-evidence').value
            .split('\n')
            .map(url => url.trim())
            .filter(url => url.length > 0);
        
        if (!contentId) {
            this.showNotification('Please enter a content ID', 'error');
            return;
        }
        
        try {
            const response = await fetch('/api/moderation/report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content_type: contentType,
                    content_id: contentId,
                    reason: reason,
                    description: description || undefined,
                    evidence_urls: evidenceUrls.length > 0 ? evidenceUrls : undefined
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showNotification('Content report submitted successfully', 'success');
                this.closeReportModal();
                this.loadModerationQueue();
            } else {
                throw new Error(result.message || 'Failed to submit report');
            }
        } catch (error) {
            console.error('Error submitting report:', error);
            this.showNotification('Failed to submit report: ' + error.message, 'error');
        }
    }
    
    async loadDashboardStats() {
        try {
            const response = await fetch('/api/moderation/stats?days=1');
            const stats = await response.json();
            
            if (response.ok) {
                document.getElementById('pending-reports').textContent = stats.pending_reports || '0';
                document.getElementById('todays-actions').textContent = stats.manual_moderated || '0';
                document.getElementById('auto-moderated').textContent = stats.auto_moderated || '0';
            }
        } catch (error) {
            console.error('Error loading dashboard stats:', error);
        }
    }
    
    // Modal management
    closeModerationModal() {
        this.closeModal(document.getElementById('moderation-modal'));
        this.selectedItem = null;
    }
    
    closeScanModal() {
        this.closeModal(document.getElementById('scan-modal'));
        document.getElementById('scan-results-container').style.display = 'none';
    }
    
    closeBulkActionModal() {
        this.closeModal(document.getElementById('bulk-action-modal'));
    }
    
    closeReportModal() {
        this.closeModal(document.getElementById('report-modal'));
    }
    
    closeModal(modal) {
        modal.style.display = 'none';
    }
    
    // Utility functions
    formatReason(reason) {
        return reason.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // Add styles
        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '15px 20px',
            borderRadius: '6px',
            color: 'white',
            fontWeight: '500',
            zIndex: '9999',
            maxWidth: '400px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
        });
        
        // Set background color based on type
        const colors = {
            success: '#4caf50',
            error: '#f44336',
            warning: '#ff9800',
            info: '#2196f3'
        };
        notification.style.backgroundColor = colors[type] || colors.info;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
}

// Global functions for modal triggers
function showScanModal() {
    document.getElementById('scan-modal').style.display = 'block';
}

function showBulkActionModal() {
    document.getElementById('bulk-action-modal').style.display = 'block';
}

function showStatsModal() {
    // TODO: Implement stats modal
    alert('Statistics modal not yet implemented');
}

function showReportModal() {
    document.getElementById('report-modal').style.display = 'block';
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.moderationDashboard = new ModerationDashboard();
});