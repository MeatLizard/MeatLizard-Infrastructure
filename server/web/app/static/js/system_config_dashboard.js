/**
 * System Configuration Dashboard JavaScript
 */

class SystemConfigDashboard {
    constructor() {
        this.currentSection = 'transcoding';
        this.config = {};
        this.presets = {};
        this.editingPreset = null;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadSystemHealth();
        this.loadConfiguration();
    }
    
    bindEvents() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.section);
            });
        });
        
        // Health refresh
        document.getElementById('refresh-health-btn').addEventListener('click', () => {
            this.loadSystemHealth();
        });
        
        // Save buttons for each section
        document.getElementById('save-transcoding-btn').addEventListener('click', () => {
            this.saveTranscodingConfig();
        });
        
        document.getElementById('save-upload-limits-btn').addEventListener('click', () => {
            this.saveUploadLimitsConfig();
        });
        
        document.getElementById('save-storage-btn').addEventListener('click', () => {
            this.saveStorageConfig();
        });
        
        document.getElementById('save-moderation-btn').addEventListener('click', () => {
            this.saveModerationConfig();
        });
        
        document.getElementById('save-analytics-btn').addEventListener('click', () => {
            this.saveAnalyticsConfig();
        });
        
        document.getElementById('save-notifications-btn').addEventListener('click', () => {
            this.saveNotificationsConfig();
        });
        
        // Preset management
        document.getElementById('add-preset-btn').addEventListener('click', () => {
            this.showPresetModal();
        });
        
        document.getElementById('save-preset-btn').addEventListener('click', () => {
            this.savePreset();
        });
        
        // Configuration management
        document.getElementById('backup-config-btn').addEventListener('click', () => {
            this.backupConfiguration();
        });
        
        document.getElementById('restore-config-btn').addEventListener('click', () => {
            this.showRestoreModal();
        });
        
        document.getElementById('reset-config-btn').addEventListener('click', () => {
            this.resetConfiguration();
        });
        
        document.getElementById('validate-config-btn').addEventListener('click', () => {
            this.validateConfiguration();
        });
        
        // Backup/Restore modal actions
        document.getElementById('download-backup-btn').addEventListener('click', () => {
            this.downloadBackup();
        });
        
        document.getElementById('restore-execute-btn').addEventListener('click', () => {
            this.executeRestore();
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
    
    async loadSystemHealth() {
        try {
            const response = await fetch('/admin/system/health');
            const health = await response.json();
            
            this.updateHealthDisplay(health);
        } catch (error) {
            console.error('Error loading system health:', error);
            this.showError('Failed to load system health status');
        }
    }
    
    updateHealthDisplay(health) {
        const indicator = document.getElementById('health-indicator');
        const text = document.getElementById('health-text');
        const details = document.getElementById('health-details');
        
        // Update overall status
        indicator.className = `status-indicator ${health.overall_status}`;
        text.textContent = health.overall_status.charAt(0).toUpperCase() + health.overall_status.slice(1);
        
        // Update health details
        details.innerHTML = '';
        
        Object.entries(health.checks).forEach(([checkName, checkData]) => {
            const checkDiv = document.createElement('div');
            checkDiv.className = `health-check ${checkData.status}`;
            
            checkDiv.innerHTML = `
                <h4>${this.formatCheckName(checkName)}</h4>
                <div class="health-check-status">
                    Status: ${checkData.status.toUpperCase()}
                    ${Object.entries(checkData).filter(([key]) => key !== 'status').map(([key, value]) => 
                        `<br>${this.formatCheckName(key)}: ${value}`
                    ).join('')}
                </div>
            `;
            
            details.appendChild(checkDiv);
        });
        
        // Show warnings and errors
        if (health.warnings.length > 0) {
            const warningsDiv = document.createElement('div');
            warningsDiv.className = 'health-check warning';
            warningsDiv.innerHTML = `
                <h4>Warnings</h4>
                <div class="health-check-status">
                    ${health.warnings.map(warning => `• ${warning}`).join('<br>')}
                </div>
            `;
            details.appendChild(warningsDiv);
        }
        
        if (health.errors.length > 0) {
            const errorsDiv = document.createElement('div');
            errorsDiv.className = 'health-check error';
            errorsDiv.innerHTML = `
                <h4>Errors</h4>
                <div class="health-check-status">
                    ${health.errors.map(error => `• ${error}`).join('<br>')}
                </div>
            `;
            details.appendChild(errorsDiv);
        }
    }
    
    formatCheckName(name) {
        return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    async loadConfiguration() {
        try {
            const response = await fetch('/admin/system/config');
            this.config = await response.json();
            
            this.populateConfigurationForms();
            this.loadTranscodingPresets();
        } catch (error) {
            console.error('Error loading configuration:', error);
            this.showError('Failed to load system configuration');
        }
    }
    
    populateConfigurationForms() {
        // Transcoding configuration
        const transcoding = this.config.transcoding || {};
        document.getElementById('max-concurrent-jobs').value = transcoding.max_concurrent_jobs || 3;
        document.getElementById('job-timeout').value = transcoding.job_timeout_minutes || 60;
        document.getElementById('hls-segment-duration').value = transcoding.hls_segment_duration || 6;
        document.getElementById('retry-attempts').value = transcoding.retry_attempts || 3;
        
        // Upload limits configuration
        const uploadLimits = this.config.upload_limits || {};
        document.getElementById('max-file-size').value = uploadLimits.max_file_size_gb || 10;
        document.getElementById('max-duration').value = uploadLimits.max_duration_hours || 4;
        document.getElementById('max-uploads-per-day').value = uploadLimits.max_uploads_per_day || 50;
        document.getElementById('max-uploads-per-hour').value = uploadLimits.max_uploads_per_hour || 10;
        
        // Allowed formats
        const allowedFormats = uploadLimits.allowed_formats || ['mp4', 'mov', 'avi', 'mkv', 'webm'];
        document.querySelectorAll('.format-checkboxes input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = allowedFormats.includes(checkbox.value);
        });
        
        // Storage configuration
        const storage = this.config.storage || {};
        document.getElementById('s3-bucket').value = storage.s3_bucket || '';
        document.getElementById('s3-region').value = storage.s3_region || '';
        document.getElementById('cdn-domain').value = storage.cdn_domain || '';
        document.getElementById('cleanup-deleted-days').value = storage.cleanup_deleted_after_days || 7;
        document.getElementById('storage-quota-warning').value = storage.storage_quota_warning_gb || 1000;
        document.getElementById('storage-quota-limit').value = storage.storage_quota_limit_gb || 2000;
        
        // Content moderation configuration
        const moderation = this.config.content_moderation || {};
        document.getElementById('auto-scan-enabled').checked = moderation.auto_scan_enabled !== false;
        document.getElementById('auto-scan-metadata').checked = moderation.auto_scan_metadata !== false;
        document.getElementById('auto-scan-visual').checked = moderation.auto_scan_visual === true;
        document.getElementById('auto-scan-audio').checked = moderation.auto_scan_audio === true;
        document.getElementById('profanity-filter-enabled').checked = moderation.profanity_filter_enabled !== false;
        document.getElementById('auto-moderate-threshold').value = moderation.auto_moderate_threshold || 'high';
        document.getElementById('report-threshold').value = moderation.report_threshold_auto_escalate || 3;
        
        // Analytics configuration
        const analytics = this.config.analytics || {};
        document.getElementById('retention-days').value = analytics.retention_days || 365;
        document.getElementById('aggregate-daily').checked = analytics.aggregate_daily !== false;
        document.getElementById('track-ip-addresses').checked = analytics.track_ip_addresses === true;
        document.getElementById('track-user-agents').checked = analytics.track_user_agents !== false;
        document.getElementById('export-enabled').checked = analytics.export_enabled !== false;
        
        // Notifications configuration
        const notifications = this.config.notifications || {};
        document.getElementById('email-enabled').checked = notifications.email_enabled === true;
        document.getElementById('webhook-enabled').checked = notifications.webhook_enabled === true;
        document.getElementById('webhook-url').value = notifications.webhook_url || '';
        document.getElementById('notify-on-upload').checked = notifications.notify_on_upload === true;
        document.getElementById('notify-on-transcoding-complete').checked = notifications.notify_on_transcoding_complete === true;
        document.getElementById('notify-on-transcoding-failed').checked = notifications.notify_on_transcoding_failed !== false;
        document.getElementById('notify-on-moderation-needed').checked = notifications.notify_on_moderation_needed !== false;
    }
    
    async loadTranscodingPresets() {
        try {
            const response = await fetch('/admin/system/transcoding/presets');
            const data = await response.json();
            this.presets = data.presets || {};
            
            this.updatePresetsTable();
        } catch (error) {
            console.error('Error loading transcoding presets:', error);
            this.showError('Failed to load transcoding presets');
        }
    }
    
    updatePresetsTable() {
        const tbody = document.getElementById('presets-table-body');
        tbody.innerHTML = '';
        
        Object.entries(this.presets).forEach(([presetName, preset]) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${presetName}</strong></td>
                <td>${preset.resolution}</td>
                <td>${preset.framerate} fps</td>
                <td>${this.formatBitrate(preset.bitrate)}</td>
                <td>${this.formatBitrate(preset.audio_bitrate)}</td>
                <td>
                    <div class="preset-enabled">
                        <input type="checkbox" ${preset.enabled ? 'checked' : ''} 
                               onchange="systemConfigDashboard.togglePresetEnabled('${presetName}', this.checked)">
                    </div>
                </td>
                <td>
                    <div class="preset-actions">
                        <button class="btn btn-sm btn-secondary" onclick="systemConfigDashboard.editPreset('${presetName}')">
                            Edit
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="systemConfigDashboard.deletePreset('${presetName}')">
                            Delete
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    }
    
    formatBitrate(bitrate) {
        if (bitrate >= 1000000) {
            return `${(bitrate / 1000000).toFixed(1)} Mbps`;
        } else if (bitrate >= 1000) {
            return `${(bitrate / 1000).toFixed(0)} kbps`;
        } else {
            return `${bitrate} bps`;
        }
    }
    
    switchTab(section) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-section="${section}"]`).classList.add('active');
        
        // Update panels
        document.querySelectorAll('.config-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        document.getElementById(`${section}-config`).classList.add('active');
        
        this.currentSection = section;
    }
    
    async saveTranscodingConfig() {
        const config = {
            max_concurrent_jobs: parseInt(document.getElementById('max-concurrent-jobs').value),
            job_timeout_minutes: parseInt(document.getElementById('job-timeout').value),
            hls_segment_duration: parseInt(document.getElementById('hls-segment-duration').value),
            retry_attempts: parseInt(document.getElementById('retry-attempts').value)
        };
        
        await this.saveConfigSection('transcoding', config);
    }
    
    async saveUploadLimitsConfig() {
        const allowedFormats = Array.from(
            document.querySelectorAll('.format-checkboxes input[type="checkbox"]:checked')
        ).map(cb => cb.value);
        
        const config = {
            max_file_size_gb: parseFloat(document.getElementById('max-file-size').value),
            max_duration_hours: parseFloat(document.getElementById('max-duration').value),
            max_uploads_per_day: parseInt(document.getElementById('max-uploads-per-day').value),
            max_uploads_per_hour: parseInt(document.getElementById('max-uploads-per-hour').value),
            allowed_formats: allowedFormats
        };
        
        await this.saveConfigSection('upload_limits', config);
    }
    
    async saveStorageConfig() {
        const config = {
            s3_bucket: document.getElementById('s3-bucket').value,
            s3_region: document.getElementById('s3-region').value,
            cdn_domain: document.getElementById('cdn-domain').value,
            cleanup_deleted_after_days: parseInt(document.getElementById('cleanup-deleted-days').value),
            storage_quota_warning_gb: parseInt(document.getElementById('storage-quota-warning').value),
            storage_quota_limit_gb: parseInt(document.getElementById('storage-quota-limit').value)
        };
        
        await this.saveConfigSection('storage', config);
    }
    
    async saveModerationConfig() {
        const config = {
            auto_scan_enabled: document.getElementById('auto-scan-enabled').checked,
            auto_scan_metadata: document.getElementById('auto-scan-metadata').checked,
            auto_scan_visual: document.getElementById('auto-scan-visual').checked,
            auto_scan_audio: document.getElementById('auto-scan-audio').checked,
            profanity_filter_enabled: document.getElementById('profanity-filter-enabled').checked,
            auto_moderate_threshold: document.getElementById('auto-moderate-threshold').value,
            report_threshold_auto_escalate: parseInt(document.getElementById('report-threshold').value)
        };
        
        await this.saveConfigSection('content_moderation', config);
    }
    
    async saveAnalyticsConfig() {
        const config = {
            retention_days: parseInt(document.getElementById('retention-days').value),
            aggregate_daily: document.getElementById('aggregate-daily').checked,
            track_ip_addresses: document.getElementById('track-ip-addresses').checked,
            track_user_agents: document.getElementById('track-user-agents').checked,
            export_enabled: document.getElementById('export-enabled').checked
        };
        
        await this.saveConfigSection('analytics', config);
    }
    
    async saveNotificationsConfig() {
        const config = {
            email_enabled: document.getElementById('email-enabled').checked,
            webhook_enabled: document.getElementById('webhook-enabled').checked,
            webhook_url: document.getElementById('webhook-url').value,
            notify_on_upload: document.getElementById('notify-on-upload').checked,
            notify_on_transcoding_complete: document.getElementById('notify-on-transcoding-complete').checked,
            notify_on_transcoding_failed: document.getElementById('notify-on-transcoding-failed').checked,
            notify_on_moderation_needed: document.getElementById('notify-on-moderation-needed').checked
        };
        
        await this.saveConfigSection('notifications', config);
    }
    
    async saveConfigSection(section, config) {
        try {
            const response = await fetch(`/admin/system/config/${section}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ config })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess(`${section} configuration saved successfully`);
                // Reload configuration to get updated values
                await this.loadConfiguration();
            } else {
                this.showError(result.detail || `Failed to save ${section} configuration`);
            }
        } catch (error) {
            console.error(`Error saving ${section} configuration:`, error);
            this.showError(`Failed to save ${section} configuration`);
        }
    }
    
    showPresetModal(presetName = null) {
        const modal = document.getElementById('preset-modal');
        const title = document.getElementById('preset-modal-title');
        const form = document.getElementById('preset-form');
        
        this.editingPreset = presetName;
        
        if (presetName) {
            title.textContent = 'Edit Transcoding Preset';
            const preset = this.presets[presetName];
            
            document.getElementById('preset-name').value = presetName;
            document.getElementById('preset-name').disabled = true;
            document.getElementById('preset-resolution').value = preset.resolution;
            document.getElementById('preset-framerate').value = preset.framerate;
            document.getElementById('preset-bitrate').value = preset.bitrate;
            document.getElementById('preset-audio-bitrate').value = preset.audio_bitrate;
            document.getElementById('preset-enabled').checked = preset.enabled;
        } else {
            title.textContent = 'Add Transcoding Preset';
            form.reset();
            document.getElementById('preset-name').disabled = false;
            document.getElementById('preset-enabled').checked = true;
        }
        
        modal.style.display = 'block';
    }
    
    async savePreset() {
        const presetName = document.getElementById('preset-name').value;
        const presetConfig = {
            resolution: document.getElementById('preset-resolution').value,
            framerate: parseInt(document.getElementById('preset-framerate').value),
            bitrate: parseInt(document.getElementById('preset-bitrate').value),
            audio_bitrate: parseInt(document.getElementById('preset-audio-bitrate').value),
            enabled: document.getElementById('preset-enabled').checked
        };
        
        try {
            const response = await fetch(`/admin/system/transcoding/presets/${presetName}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(presetConfig)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess(`Preset ${presetName} saved successfully`);
                this.closeModal(document.getElementById('preset-modal'));
                await this.loadTranscodingPresets();
            } else {
                this.showError(result.detail || 'Failed to save preset');
            }
        } catch (error) {
            console.error('Error saving preset:', error);
            this.showError('Failed to save preset');
        }
    }
    
    editPreset(presetName) {
        this.showPresetModal(presetName);
    }
    
    async deletePreset(presetName) {
        const confirmed = await this.showConfirmation(
            `Are you sure you want to delete the preset "${presetName}"? This action cannot be undone.`
        );
        
        if (!confirmed) return;
        
        try {
            const response = await fetch(`/admin/system/transcoding/presets/${presetName}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess(`Preset ${presetName} deleted successfully`);
                await this.loadTranscodingPresets();
            } else {
                this.showError(result.detail || 'Failed to delete preset');
            }
        } catch (error) {
            console.error('Error deleting preset:', error);
            this.showError('Failed to delete preset');
        }
    }
    
    async togglePresetEnabled(presetName, enabled) {
        const preset = { ...this.presets[presetName], enabled };
        
        try {
            const response = await fetch(`/admin/system/transcoding/presets/${presetName}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(preset)
            });
            
            if (response.ok) {
                this.presets[presetName].enabled = enabled;
                this.showSuccess(`Preset ${presetName} ${enabled ? 'enabled' : 'disabled'}`);
            } else {
                // Revert checkbox state
                const checkbox = event.target;
                checkbox.checked = !enabled;
                this.showError('Failed to update preset');
            }
        } catch (error) {
            console.error('Error updating preset:', error);
            // Revert checkbox state
            const checkbox = event.target;
            checkbox.checked = !enabled;
            this.showError('Failed to update preset');
        }
    }
    
    async backupConfiguration() {
        try {
            const response = await fetch('/admin/system/config/backup', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showBackupModal(result.backup_data);
            } else {
                this.showError(result.detail || 'Failed to create backup');
            }
        } catch (error) {
            console.error('Error creating backup:', error);
            this.showError('Failed to create backup');
        }
    }
    
    showBackupModal(backupData) {
        const modal = document.getElementById('backup-restore-modal');
        const title = document.getElementById('backup-restore-title');
        const backupContent = document.getElementById('backup-content');
        const restoreContent = document.getElementById('restore-content');
        const backupJson = document.getElementById('backup-json');
        const downloadBtn = document.getElementById('download-backup-btn');
        const restoreBtn = document.getElementById('restore-execute-btn');
        
        title.textContent = 'Configuration Backup';
        backupContent.style.display = 'block';
        restoreContent.style.display = 'none';
        downloadBtn.style.display = 'inline-block';
        restoreBtn.style.display = 'none';
        
        backupJson.value = JSON.stringify(backupData, null, 2);
        
        modal.style.display = 'block';
    }
    
    showRestoreModal() {
        const modal = document.getElementById('backup-restore-modal');
        const title = document.getElementById('backup-restore-title');
        const backupContent = document.getElementById('backup-content');
        const restoreContent = document.getElementById('restore-content');
        const downloadBtn = document.getElementById('download-backup-btn');
        const restoreBtn = document.getElementById('restore-execute-btn');
        
        title.textContent = 'Restore Configuration';
        backupContent.style.display = 'none';
        restoreContent.style.display = 'block';
        downloadBtn.style.display = 'none';
        restoreBtn.style.display = 'inline-block';
        
        document.getElementById('restore-json').value = '';
        
        modal.style.display = 'block';
    }
    
    downloadBackup() {
        const backupJson = document.getElementById('backup-json').value;
        const blob = new Blob([backupJson], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `meatlizard-config-backup-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
    }
    
    async executeRestore() {
        const restoreJson = document.getElementById('restore-json').value;
        
        if (!restoreJson.trim()) {
            this.showError('Please paste backup JSON data');
            return;
        }
        
        let backupData;
        try {
            backupData = JSON.parse(restoreJson);
        } catch (error) {
            this.showError('Invalid JSON format');
            return;
        }
        
        const confirmed = await this.showConfirmation(
            'Are you sure you want to restore this configuration? This will overwrite all current settings.'
        );
        
        if (!confirmed) return;
        
        try {
            const response = await fetch('/admin/system/config/restore', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ backup_data: backupData })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess('Configuration restored successfully');
                this.closeModal(document.getElementById('backup-restore-modal'));
                await this.loadConfiguration();
                await this.loadSystemHealth();
            } else {
                this.showError(result.detail || 'Failed to restore configuration');
            }
        } catch (error) {
            console.error('Error restoring configuration:', error);
            this.showError('Failed to restore configuration');
        }
    }
    
    async resetConfiguration() {
        const confirmed = await this.showConfirmation(
            'Are you sure you want to reset all configuration to defaults? This action cannot be undone.'
        );
        
        if (!confirmed) return;
        
        try {
            const response = await fetch('/admin/system/config/reset', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showSuccess('Configuration reset to defaults');
                await this.loadConfiguration();
                await this.loadSystemHealth();
            } else {
                this.showError(result.detail || 'Failed to reset configuration');
            }
        } catch (error) {
            console.error('Error resetting configuration:', error);
            this.showError('Failed to reset configuration');
        }
    }
    
    async validateConfiguration() {
        // Collect all current form values
        const configData = {};
        
        // Add validation logic here based on current form values
        // For now, we'll just validate the current loaded config
        
        try {
            const response = await fetch('/admin/system/validate-config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(this.config)
            });
            
            const result = await response.json();
            
            if (result.valid) {
                this.showSuccess('Configuration is valid');
            } else {
                this.showError(`Configuration validation failed:\n${result.errors.join('\n')}`);
            }
        } catch (error) {
            console.error('Error validating configuration:', error);
            this.showError('Failed to validate configuration');
        }
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
}

// Initialize the dashboard when the page loads
let systemConfigDashboard;
document.addEventListener('DOMContentLoaded', () => {
    systemConfigDashboard = new SystemConfigDashboard();
});