// Media Import JavaScript

class MediaImportManager {
    constructor() {
        this.importJobs = [];
        this.importPresets = [];
        this.refreshInterval = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadImportPresets();
        this.loadImportJobs();
        this.startAutoRefresh();
    }

    bindEvents() {
        // Extract info button
        document.getElementById('extractInfoBtn').addEventListener('click', () => {
            this.extractMediaInfo();
        });

        // Import form submission
        document.getElementById('importForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startImport();
        });

        // Audio only checkbox
        document.getElementById('audioOnly').addEventListener('change', (e) => {
            const audioOptions = document.querySelector('.audio-options');
            if (e.target.checked) {
                audioOptions.classList.add('show');
            } else {
                audioOptions.classList.remove('show');
            }
        });

        // Import preset selection
        document.getElementById('importPreset').addEventListener('change', (e) => {
            if (e.target.value) {
                this.loadPresetSettings(e.target.value);
            }
        });

        // Save preset button
        document.getElementById('savePresetBtn').addEventListener('click', () => {
            this.showSavePresetModal();
        });

        // Save preset form
        document.getElementById('savePresetForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.savePreset();
        });

        // Status filter
        document.getElementById('statusFilter').addEventListener('change', () => {
            this.loadImportJobs();
        });

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadImportJobs();
        });

        // URL input validation
        document.getElementById('sourceUrl').addEventListener('input', (e) => {
            this.validateUrl(e.target.value);
        });
    }

    async extractMediaInfo() {
        const url = document.getElementById('sourceUrl').value;
        if (!url) {
            this.showError('Please enter a URL');
            return;
        }

        const btn = document.getElementById('extractInfoBtn');
        const originalText = btn.textContent;
        btn.innerHTML = '<span class="spinner"></span>Extracting...';
        btn.disabled = true;

        try {
            const response = await fetch('/api/import/extract-info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to extract media info');
            }

            const mediaInfo = await response.json();
            this.displayMediaInfo(mediaInfo);

        } catch (error) {
            this.showError(`Failed to extract media info: ${error.message}`);
            this.hideMediaInfo();
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

    displayMediaInfo(info) {
        document.getElementById('mediaTitle').textContent = info.title || '-';
        document.getElementById('mediaUploader').textContent = info.uploader || '-';
        document.getElementById('mediaPlatform').textContent = info.platform || '-';
        document.getElementById('mediaDuration').textContent = 
            info.duration ? this.formatDuration(info.duration) : '-';
        document.getElementById('mediaViews').textContent = 
            info.view_count ? this.formatNumber(info.view_count) : '-';

        const thumbnail = document.getElementById('mediaThumbnail');
        if (info.thumbnail_url) {
            thumbnail.src = info.thumbnail_url;
            thumbnail.style.display = 'block';
        } else {
            thumbnail.style.display = 'none';
        }

        document.getElementById('mediaInfo').style.display = 'block';
    }

    hideMediaInfo() {
        document.getElementById('mediaInfo').style.display = 'none';
    }

    async startImport() {
        const formData = this.getFormData();
        
        if (!formData.url) {
            this.showError('Please enter a URL');
            return;
        }

        const submitBtn = document.querySelector('#importForm button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.innerHTML = '<span class="spinner"></span>Starting Import...';
        submitBtn.disabled = true;

        try {
            const response = await fetch('/api/import/jobs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: formData.url,
                    config: formData.config
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start import');
            }

            const job = await response.json();
            this.showSuccess(`Import job started successfully! Job ID: ${job.id}`);
            this.loadImportJobs(); // Refresh the job list
            this.resetForm();

        } catch (error) {
            this.showError(`Failed to start import: ${error.message}`);
        } finally {
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }
    }

    getFormData() {
        const form = document.getElementById('importForm');
        const formData = new FormData(form);
        
        // Get quality presets
        const qualityPresets = [];
        document.querySelectorAll('input[name="qualityPresets"]:checked').forEach(cb => {
            qualityPresets.push(cb.value);
        });

        const config = {
            max_height: formData.get('maxHeight') ? parseInt(formData.get('maxHeight')) : null,
            max_fps: formData.get('maxFps') ? parseInt(formData.get('maxFps')) : null,
            max_filesize: formData.get('maxFilesize') || null,
            audio_only: formData.get('audioOnly') === 'on',
            audio_format: formData.get('audioFormat') || 'mp3',
            preferred_codec: formData.get('preferredCodec') || null,
            quality_presets: qualityPresets,
            preserve_metadata: formData.get('preserveMetadata') === 'on',
            auto_publish: formData.get('autoPublish') === 'on',
            category: formData.get('category') || null
        };

        return {
            url: formData.get('sourceUrl'),
            config: config
        };
    }

    async loadImportJobs() {
        const status = document.getElementById('statusFilter').value;
        const params = new URLSearchParams();
        if (status) params.append('status', status);

        try {
            const response = await fetch(`/api/import/jobs?${params}`);
            if (!response.ok) throw new Error('Failed to load import jobs');

            this.importJobs = await response.json();
            this.renderImportJobs();

        } catch (error) {
            this.showError(`Failed to load import jobs: ${error.message}`);
        }
    }

    renderImportJobs() {
        const container = document.getElementById('importJobs');
        
        if (this.importJobs.length === 0) {
            container.innerHTML = '<p>No import jobs found.</p>';
            return;
        }

        container.innerHTML = this.importJobs.map(job => this.renderImportJob(job)).join('');
    }

    renderImportJob(job) {
        const createdAt = new Date(job.created_at).toLocaleString();
        const progressPercent = job.progress_percent || 0;

        return `
            <div class="import-job">
                <div class="job-header">
                    <h4 class="job-title">${job.original_title || 'Untitled'}</h4>
                    <span class="job-status ${job.status}">${job.status}</span>
                </div>
                
                <div class="job-details">
                    <div class="job-detail">
                        <label>Platform</label>
                        <span>${job.platform}</span>
                    </div>
                    <div class="job-detail">
                        <label>Uploader</label>
                        <span>${job.original_uploader || '-'}</span>
                    </div>
                    <div class="job-detail">
                        <label>Created</label>
                        <span>${createdAt}</span>
                    </div>
                    <div class="job-detail">
                        <label>Job ID</label>
                        <span>${job.id}</span>
                    </div>
                </div>

                ${job.status === 'downloading' || job.status === 'processing' ? `
                    <div class="job-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${progressPercent}%"></div>
                        </div>
                        <small>${progressPercent}% complete</small>
                    </div>
                ` : ''}

                ${job.error_message ? `
                    <div class="job-error">
                        <strong>Error:</strong> ${job.error_message}
                    </div>
                ` : ''}

                <div class="job-actions">
                    <a href="${job.source_url}" target="_blank" class="btn btn-secondary">View Source</a>
                    ${job.video_id ? `
                        <a href="/video/${job.video_id}" class="btn btn-primary">View Video</a>
                    ` : ''}
                </div>
            </div>
        `;
    }

    async loadImportPresets() {
        try {
            const response = await fetch('/api/import/presets');
            if (!response.ok) throw new Error('Failed to load presets');

            this.importPresets = await response.json();
            this.renderPresetOptions();

        } catch (error) {
            console.error('Failed to load import presets:', error);
        }
    }

    renderPresetOptions() {
        const select = document.getElementById('importPreset');
        const currentOptions = select.innerHTML;
        
        const presetOptions = this.importPresets.map(preset => 
            `<option value="${preset.id}">${preset.name}</option>`
        ).join('');

        select.innerHTML = currentOptions + presetOptions;
    }

    loadPresetSettings(presetId) {
        const preset = this.importPresets.find(p => p.id === presetId);
        if (!preset) return;

        const config = preset.config;
        
        // Set form values based on preset
        if (config.max_height) document.getElementById('maxHeight').value = config.max_height;
        if (config.max_fps) document.getElementById('maxFps').value = config.max_fps;
        if (config.max_filesize) document.getElementById('maxFilesize').value = config.max_filesize;
        if (config.preferred_codec) document.getElementById('preferredCodec').value = config.preferred_codec;
        
        document.getElementById('audioOnly').checked = config.audio_only || false;
        document.getElementById('audioFormat').value = config.audio_format || 'mp3';
        document.getElementById('preserveMetadata').checked = config.preserve_metadata !== false;
        document.getElementById('autoPublish').checked = config.auto_publish || false;
        document.getElementById('category').value = config.category || '';

        // Set quality presets
        document.querySelectorAll('input[name="qualityPresets"]').forEach(cb => {
            cb.checked = config.quality_presets && config.quality_presets.includes(cb.value);
        });

        // Show/hide audio options
        const audioOptions = document.querySelector('.audio-options');
        if (config.audio_only) {
            audioOptions.classList.add('show');
        } else {
            audioOptions.classList.remove('show');
        }
    }

    showSavePresetModal() {
        document.getElementById('savePresetModal').style.display = 'flex';
    }

    async savePreset() {
        const name = document.getElementById('presetName').value;
        const description = document.getElementById('presetDescription').value;
        
        if (!name) {
            this.showError('Please enter a preset name');
            return;
        }

        const formData = this.getFormData();

        try {
            const response = await fetch('/api/import/presets', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    description: description,
                    config: formData.config
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to save preset');
            }

            this.showSuccess('Preset saved successfully!');
            this.closeModal();
            this.loadImportPresets(); // Refresh presets

        } catch (error) {
            this.showError(`Failed to save preset: ${error.message}`);
        }
    }

    closeModal() {
        document.getElementById('savePresetModal').style.display = 'none';
        document.getElementById('savePresetForm').reset();
    }

    resetForm() {
        document.getElementById('importForm').reset();
        this.hideMediaInfo();
        document.querySelector('.audio-options').classList.remove('show');
        
        // Reset quality presets to default
        document.querySelectorAll('input[name="qualityPresets"]').forEach(cb => {
            cb.checked = cb.value === '720p_30fps';
        });
    }

    validateUrl(url) {
        const extractBtn = document.getElementById('extractInfoBtn');
        
        if (!url) {
            extractBtn.disabled = true;
            return;
        }

        // Basic URL validation
        try {
            new URL(url);
            extractBtn.disabled = false;
        } catch {
            extractBtn.disabled = true;
        }
    }

    startAutoRefresh() {
        // Refresh jobs every 30 seconds if there are active jobs
        this.refreshInterval = setInterval(() => {
            const hasActiveJobs = this.importJobs.some(job => 
                job.status === 'queued' || job.status === 'downloading' || job.status === 'processing'
            );
            
            if (hasActiveJobs) {
                this.loadImportJobs();
            }
        }, 30000);
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

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        } else {
            return num.toString();
        }
    }

    showError(message) {
        // Simple error display - could be enhanced with a proper notification system
        alert('Error: ' + message);
    }

    showSuccess(message) {
        // Simple success display - could be enhanced with a proper notification system
        alert('Success: ' + message);
    }
}

// Global function for modal
function closeModal() {
    document.getElementById('savePresetModal').style.display = 'none';
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new MediaImportManager();
});