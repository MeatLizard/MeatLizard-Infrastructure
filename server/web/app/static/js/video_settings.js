/**
 * Video Settings JavaScript
 * Handles video visibility, permissions, and access control
 */

class VideoSettingsManager {
    constructor() {
        this.videoId = this.getVideoIdFromUrl();
        this.currentVisibility = null;
        this.permissions = [];
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadPermissions();
        this.loadAnalytics();
        this.updateVisibilityUI();
    }
    
    getVideoIdFromUrl() {
        // Extract video ID from URL path or query params
        const pathParts = window.location.pathname.split('/');
        return pathParts[pathParts.length - 2]; // Assuming URL like /videos/{id}/settings
    }
    
    bindEvents() {
        // Visibility radio buttons
        document.querySelectorAll('input[name="visibility"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.updateVisibilityUI();
            });
        });
        
        // Save visibility button
        document.getElementById('save-visibility').addEventListener('click', () => {
            this.saveVisibility();
        });
        
        // Grant permission button
        document.getElementById('grant-permission').addEventListener('click', () => {
            this.showUserSearchModal();
        });
        
        // User search input
        document.getElementById('user-search').addEventListener('input', (e) => {
            this.searchUsers(e.target.value);
        });
        
        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.closeModal(e.target.closest('.modal'));
            });
        });
        
        // Confirmation modal buttons
        document.getElementById('confirmation-cancel').addEventListener('click', () => {
            this.closeModal(document.getElementById('confirmation-modal'));
        });
        
        document.getElementById('confirmation-confirm').addEventListener('click', () => {
            this.executeConfirmedAction();
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
    
    updateVisibilityUI() {
        const selectedVisibility = document.querySelector('input[name="visibility"]:checked').value;
        this.currentVisibility = selectedVisibility;
        
        // Update visibility option styling
        document.querySelectorAll('.visibility-option').forEach(option => {
            option.classList.remove('selected');
        });
        
        const selectedOption = document.querySelector(`[data-visibility="${selectedVisibility}"]`);
        if (selectedOption) {
            selectedOption.classList.add('selected');
        }
        
        // Show/hide permissions section
        const permissionsSection = document.getElementById('permissions-section');
        if (selectedVisibility === 'private') {
            permissionsSection.style.display = 'block';
        } else {
            permissionsSection.style.display = 'none';
        }
    }
    
    async saveVisibility() {
        const selectedVisibility = document.querySelector('input[name="visibility"]:checked').value;
        const saveButton = document.getElementById('save-visibility');
        
        try {
            saveButton.disabled = true;
            saveButton.textContent = 'Saving...';
            
            const response = await fetch('/api/videos/update-visibility', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    video_id: this.videoId,
                    visibility: selectedVisibility
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showNotification('Visibility updated successfully', 'success');
                this.updateVisibilityUI();
            } else {
                throw new Error(result.message || 'Failed to update visibility');
            }
        } catch (error) {
            console.error('Error updating visibility:', error);
            this.showNotification('Failed to update visibility: ' + error.message, 'error');
        } finally {
            saveButton.disabled = false;
            saveButton.textContent = 'Save Visibility Settings';
        }
    }
    
    async loadPermissions() {
        if (this.currentVisibility !== 'private') {
            return;
        }
        
        try {
            const response = await fetch(`/api/videos/permissions/${this.videoId}`);
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.permissions = result.permissions;
                this.renderPermissions();
            } else {
                console.error('Failed to load permissions:', result.message);
            }
        } catch (error) {
            console.error('Error loading permissions:', error);
        }
    }
    
    renderPermissions() {
        const container = document.getElementById('permissions-container');
        
        if (this.permissions.length === 0) {
            container.innerHTML = '<p class="no-permissions">No additional permissions granted.</p>';
            return;
        }
        
        const permissionsHtml = this.permissions.map(permission => `
            <div class="permission-item" data-permission-id="${permission.id}">
                <div class="permission-info">
                    <div class="permission-user">${permission.user_name}</div>
                    <div class="permission-details">
                        <span class="permission-type ${permission.permission_type}">${permission.permission_type}</span>
                        <span class="permission-granted">Granted by ${permission.granted_by_name}</span>
                        <span class="permission-date">${this.formatDate(permission.created_at)}</span>
                        ${permission.expires_at ? `<span class="permission-expires">Expires: ${this.formatDate(permission.expires_at)}</span>` : ''}
                    </div>
                </div>
                <div class="permission-actions">
                    <button class="btn btn-danger btn-small" onclick="videoSettings.revokePermission('${permission.id}', '${permission.user_name}')">
                        Revoke
                    </button>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = permissionsHtml;
    }
    
    showUserSearchModal() {
        const modal = document.getElementById('user-search-modal');
        const searchInput = document.getElementById('user-search');
        
        searchInput.value = '';
        document.getElementById('user-search-results').innerHTML = '';
        
        modal.style.display = 'block';
        searchInput.focus();
    }
    
    async searchUsers(query) {
        if (query.length < 2) {
            document.getElementById('user-search-results').innerHTML = '';
            return;
        }
        
        try {
            const response = await fetch(`/api/users/search?q=${encodeURIComponent(query)}`);
            const users = await response.json();
            
            this.renderUserSearchResults(users);
        } catch (error) {
            console.error('Error searching users:', error);
            document.getElementById('user-search-results').innerHTML = 
                '<div class="error">Error searching users</div>';
        }
    }
    
    renderUserSearchResults(users) {
        const container = document.getElementById('user-search-results');
        
        if (users.length === 0) {
            container.innerHTML = '<div class="no-results">No users found</div>';
            return;
        }
        
        const usersHtml = users.map(user => `
            <div class="user-result" onclick="videoSettings.selectUser('${user.id}', '${user.display_label}')">
                <div class="user-avatar">${user.display_label.charAt(0).toUpperCase()}</div>
                <div class="user-info">
                    <div class="user-name">${user.display_label}</div>
                    ${user.email ? `<div class="user-email">${user.email}</div>` : ''}
                </div>
            </div>
        `).join('');
        
        container.innerHTML = usersHtml;
    }
    
    selectUser(userId, userName) {
        this.closeModal(document.getElementById('user-search-modal'));
        this.grantPermission(userId, userName);
    }
    
    async grantPermission(userId, userName) {
        const permissionType = document.getElementById('permission-type').value;
        const expiresAt = document.getElementById('expires-at').value;
        
        try {
            const requestBody = {
                video_id: this.videoId,
                user_id: userId,
                permission_type: permissionType
            };
            
            if (expiresAt) {
                requestBody.expires_at = new Date(expiresAt).toISOString();
            }
            
            const response = await fetch('/api/videos/grant-permission', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showNotification(`Permission granted to ${userName}`, 'success');
                this.loadPermissions(); // Reload permissions list
                
                // Clear form
                document.getElementById('permission-type').value = 'view';
                document.getElementById('expires-at').value = '';
            } else {
                throw new Error(result.message || 'Failed to grant permission');
            }
        } catch (error) {
            console.error('Error granting permission:', error);
            this.showNotification('Failed to grant permission: ' + error.message, 'error');
        }
    }
    
    revokePermission(permissionId, userName) {
        this.showConfirmationModal(
            'Revoke Permission',
            `Are you sure you want to revoke access for ${userName}?`,
            () => this.executeRevokePermission(permissionId, userName)
        );
    }
    
    async executeRevokePermission(permissionId, userName) {
        try {
            // Find the permission to get user_id
            const permission = this.permissions.find(p => p.id === permissionId);
            if (!permission) {
                throw new Error('Permission not found');
            }
            
            const response = await fetch('/api/videos/revoke-permission', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    video_id: this.videoId,
                    user_id: permission.user_id
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showNotification(`Permission revoked from ${userName}`, 'success');
                this.loadPermissions(); // Reload permissions list
            } else {
                throw new Error(result.message || 'Failed to revoke permission');
            }
        } catch (error) {
            console.error('Error revoking permission:', error);
            this.showNotification('Failed to revoke permission: ' + error.message, 'error');
        }
    }
    
    async loadAnalytics() {
        try {
            const response = await fetch(`/api/videos/${this.videoId}/analytics`);
            const analytics = await response.json();
            
            if (response.ok) {
                this.updateAnalyticsDisplay(analytics);
            }
        } catch (error) {
            console.error('Error loading analytics:', error);
        }
    }
    
    updateAnalyticsDisplay(analytics) {
        document.getElementById('total-views').textContent = analytics.total_views || '0';
        document.getElementById('unique-viewers').textContent = analytics.unique_viewers || '0';
        document.getElementById('access-attempts').textContent = analytics.access_attempts || '0';
        document.getElementById('denied-access').textContent = analytics.denied_access || '0';
    }
    
    showConfirmationModal(title, message, confirmCallback) {
        const modal = document.getElementById('confirmation-modal');
        
        document.getElementById('confirmation-title').textContent = title;
        document.getElementById('confirmation-message').textContent = message;
        
        this.confirmCallback = confirmCallback;
        modal.style.display = 'block';
    }
    
    executeConfirmedAction() {
        if (this.confirmCallback) {
            this.confirmCallback();
            this.confirmCallback = null;
        }
        this.closeModal(document.getElementById('confirmation-modal'));
    }
    
    closeModal(modal) {
        modal.style.display = 'none';
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
    
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.videoSettings = new VideoSettingsManager();
});