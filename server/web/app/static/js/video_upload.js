// Video Upload JavaScript

class VideoUploadManager {
    constructor() {
        this.currentFile = null;
        this.uploadSession = null;
        this.tags = [];
        this.popularTags = [];
        this.qualityPresets = [];
        this.uploadProgress = {
            percent: 0,
            uploadedSize: 0,
            totalSize: 0,
            speed: 0,
            startTime: null
        };
        
        this.initializeElements();
        this.bindEvents();
        this.loadPopularTags();
    }
    
    initializeElements() {
        // Form elements
        this.form = document.getElementById('videoUploadForm');
        this.fileInput = document.getElementById('videoFile');
        this.titleInput = document.getElementById('videoTitle');
        this.descriptionInput = document.getElementById('videoDescription');
        this.tagsInput = document.getElementById('videoTags');
        
        // Display elements
        this.fileInfo = document.getElementById('fileInfo');
        this.fileName = document.getElementById('fileName');
        this.fileSize = document.getElementById('fileSize');
        this.fileType = document.getElementById('fileType');
        this.tagsContainer = document.getElementById('tagsContainer');
        this.qualitySection = document.getElementById('qualitySection');
        this.qualityPresets = document.getElementById('qualityPresets');
        this.progressSection = document.getElementById('progressSection');
        this.uploadResult = document.getElementById('uploadResult');
        
        // Counter elements
        this.titleCounter = document.getElementById('titleCounter');
        this.descriptionCounter = document.getElementById('descriptionCounter');
        
        // Progress elements
        this.progressFill = document.getElementById('progressFill');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressStatus = document.getElementById('progressStatus');
        this.uploadedSize = document.getElementById('uploadedSize');
        this.totalSize = document.getElementById('totalSize');
        this.uploadSpeed = document.getElementById('uploadSpeed');
        this.timeRemaining = document.getElementById('timeRemaining');
        
        // Button elements
        this.analyzeButton = document.getElementById('analyzeButton');
        this.uploadButton = document.getElementById('uploadButton');
        this.cancelButton = document.getElementById('cancelButton');
        this.uploadAnotherButton = document.getElementById('uploadAnotherButton');
        
        // Thumbnail elements
        this.thumbnailSection = document.getElementById('thumbnailSection');
        this.thumbnailGrid = document.getElementById('thumbnailGrid');
        this.regenerateThumbnailsButton = document.getElementById('regenerateThumbnails');
        this.autoSelectThumbnailButton = document.getElementById('autoSelectThumbnail');
        
        // Modal elements
        this.popularTagsModal = document.getElementById('popularTagsModal');
        this.showPopularTagsButton = document.getElementById('showPopularTags');
        this.closePopularTagsButton = document.getElementById('closePopularTags');
        this.popularTagsList = document.getElementById('popularTagsList');
        
        // Result elements
        this.resultVideoId = document.getElementById('resultVideoId');
        this.resultStatus = document.getElementById('resultStatus');
    }
    
    bindEvents() {
        // File input change
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        
        // Character counters
        this.titleInput.addEventListener('input', () => this.updateCharCounter('title'));
        this.descriptionInput.addEventListener('input', () => this.updateCharCounter('description'));
        
        // Tags input
        this.tagsInput.addEventListener('keydown', (e) => this.handleTagsInput(e));
        this.tagsInput.addEventListener('blur', () => this.addTagFromInput());
        
        // Button events
        this.analyzeButton.addEventListener('click', () => this.analyzeVideo());
        this.cancelButton.addEventListener('click', () => this.cancelUpload());
        this.uploadAnotherButton.addEventListener('click', () => this.resetForm());
        
        // Thumbnail events
        this.regenerateThumbnailsButton.addEventListener('click', () => this.regenerateThumbnails());
        this.autoSelectThumbnailButton.addEventListener('click', () => this.autoSelectThumbnail());
        
        // Modal events
        this.showPopularTagsButton.addEventListener('click', () => this.showPopularTagsModal());
        this.closePopularTagsButton.addEventListener('click', () => this.hidePopularTagsModal());
        
        // Click outside modal to close
        this.popularTagsModal.addEventListener('click', (e) => {
            if (e.target === this.popularTagsModal) {
                this.hidePopularTagsModal();
            }
        });
    }
    
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file) {
            this.hideFileInfo();
            return;
        }
        
        this.currentFile = file;
        this.showFileInfo(file);
        this.analyzeButton.disabled = false;
        
        // Auto-analyze if file is small enough
        if (file.size < 100 * 1024 * 1024) { // 100MB
            setTimeout(() => this.analyzeVideo(), 500);
        }
    }
    
    showFileInfo(file) {
        this.fileName.textContent = file.name;
        this.fileSize.textContent = this.formatFileSize(file.size);
        this.fileType.textContent = file.type || 'Unknown';
        this.fileInfo.style.display = 'block';
    }
    
    hideFileInfo() {
        this.fileInfo.style.display = 'none';
        this.currentFile = null;
        this.analyzeButton.disabled = true;
        this.uploadButton.disabled = true;
        this.qualitySection.style.display = 'none';
    }
    
    async analyzeVideo() {
        if (!this.currentFile) return;
        
        this.analyzeButton.disabled = true;
        this.analyzeButton.textContent = 'Analyzing...';
        
        try {
            const formData = new FormData();
            formData.append('file', this.currentFile);
            
            const response = await fetch('/api/video/analyze', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Analysis failed: ${response.statusText}`);
            }
            
            const analysis = await response.json();
            
            if (analysis.is_valid) {
                this.showQualityPresets(analysis.available_presets);
                this.uploadButton.disabled = false;
                this.showSuccess('Video analysis complete! Select quality presets and upload.');
            } else {
                this.showError(`Video analysis failed: ${analysis.error_message}`);
            }
            
        } catch (error) {
            console.error('Analysis error:', error);
            this.showError(`Analysis failed: ${error.message}`);
        } finally {
            this.analyzeButton.disabled = false;
            this.analyzeButton.textContent = 'Analyze Video';
        }
    }
    
    showQualityPresets(presets) {
        this.qualityPresets.innerHTML = '';
        
        presets.forEach((preset, index) => {
            const presetDiv = document.createElement('div');
            presetDiv.className = 'quality-preset';
            
            const isDefault = preset.is_default || preset.is_recommended;
            
            presetDiv.innerHTML = `
                <label>
                    <input type="checkbox" name="quality_preset" value="${preset.name}" ${isDefault ? 'checked' : ''}>
                    ${preset.resolution.toUpperCase()} @ ${preset.framerate.replace('fps', ' FPS')}
                </label>
                <div class="quality-details">
                    Resolution: ${preset.width}×${preset.height}<br>
                    Frame Rate: ${preset.framerate.replace('fps', ' FPS')}<br>
                    Bitrate: ${(preset.target_bitrate / 1000000).toFixed(1)} Mbps<br>
                    ${preset.estimated_file_size_mb ? `Est. Size: ${preset.estimated_file_size_mb} MB<br>` : ''}
                    ${preset.estimated_processing_time_minutes ? `Est. Time: ${preset.estimated_processing_time_minutes} min<br>` : ''}
                    ${preset.description}
                </div>
            `;
            
            this.qualityPresets.appendChild(presetDiv);
        });
        
        this.qualitySection.style.display = 'block';
    }
    
    getResolutionDetails(resolution) {
        const resolutions = {
            '480p': '854×480',
            '720p': '1280×720',
            '1080p': '1920×1080',
            '1440p': '2560×1440',
            '2160p': '3840×2160'
        };
        return resolutions[resolution] || resolution;
    }
    
    async handleFormSubmit(event) {
        event.preventDefault();
        
        if (!this.validateForm()) {
            return;
        }
        
        this.uploadButton.disabled = true;
        this.uploadButton.textContent = 'Starting Upload...';
        this.progressSection.style.display = 'block';
        
        try {
            await this.startUpload();
        } catch (error) {
            console.error('Upload error:', error);
            this.showError(`Upload failed: ${error.message}`);
            this.uploadButton.disabled = false;
            this.uploadButton.textContent = 'Upload Video';
        }
    }
    
    validateForm() {
        let isValid = true;
        
        // Validate title
        if (!this.titleInput.value.trim()) {
            this.showFieldError('title', 'Title is required');
            isValid = false;
        } else if (this.titleInput.value.length > 100) {
            this.showFieldError('title', 'Title must be 100 characters or less');
            isValid = false;
        } else {
            this.clearFieldError('title');
        }
        
        // Validate description
        if (this.descriptionInput.value.length > 5000) {
            this.showFieldError('description', 'Description must be 5000 characters or less');
            isValid = false;
        } else {
            this.clearFieldError('description');
        }
        
        // Validate file
        if (!this.currentFile) {
            this.showError('Please select a video file');
            isValid = false;
        }
        
        // Validate quality presets
        const selectedPresets = this.getSelectedQualityPresets();
        if (selectedPresets.length === 0) {
            this.showError('Please select at least one quality preset');
            isValid = false;
        }
        
        return isValid;
    }
    
    getSelectedQualityPresets() {
        const checkboxes = document.querySelectorAll('input[name="quality_preset"]:checked');
        return Array.from(checkboxes).map(cb => cb.value);
    }
    
    async startUpload() {
        // Prepare metadata
        const metadata = {
            title: this.titleInput.value.trim(),
            description: this.descriptionInput.value.trim() || null,
            tags: this.tags,
            filename: this.currentFile.name,
            file_size: this.currentFile.size,
            mime_type: this.currentFile.type,
            total_chunks: 1 // Simple upload for now
        };
        
        // Initiate upload
        const response = await fetch('/api/video/upload/initiate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(metadata)
        });
        
        if (!response.ok) {
            throw new Error(`Failed to initiate upload: ${response.statusText}`);
        }
        
        const uploadSession = await response.json();
        this.uploadSession = uploadSession;
        
        // Start actual upload
        await this.uploadFile();
    }
    
    async uploadFile() {
        this.uploadProgress.startTime = Date.now();
        this.uploadProgress.totalSize = this.currentFile.size;
        
        const formData = new FormData();
        formData.append('chunk', this.currentFile);
        
        // Show cancel button
        this.cancelButton.style.display = 'inline-block';
        this.uploadButton.style.display = 'none';
        
        try {
            const response = await fetch(`/api/video/upload/${this.uploadSession.session_id}/chunk/1`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Chunk upload failed: ${response.statusText}`);
            }
            
            // Complete upload
            await this.completeUpload();
            
        } catch (error) {
            throw error;
        }
    }
    
    async completeUpload() {
        const selectedPresets = this.getSelectedQualityPresets();
        
        const response = await fetch(`/api/video/upload/${this.uploadSession.session_id}/complete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                quality_presets: selectedPresets
            })
        });
        
        if (!response.ok) {
            throw new Error(`Failed to complete upload: ${response.statusText}`);
        }
        
        const result = await response.json();
        this.showUploadComplete(result);
    }
    
    showUploadComplete(result) {
        this.resultVideoId.textContent = result.video_id;
        this.resultStatus.textContent = result.status;
        
        // Update progress to 100%
        this.updateProgress(100, this.currentFile.size, this.currentFile.size);
        this.progressStatus.textContent = 'Upload complete!';
        
        // Load thumbnails if available
        this.loadVideoThumbnails(result.video_id);
        
        // Show thumbnail section
        this.thumbnailSection.style.display = 'block';
        
        // Hide form and show result
        this.form.style.display = 'none';
        this.uploadResult.style.display = 'block';
    }
    
    updateProgress(percent, uploaded, total) {
        this.uploadProgress.percent = percent;
        this.uploadProgress.uploadedSize = uploaded;
        
        this.progressFill.style.width = `${percent}%`;
        this.progressPercent.textContent = `${Math.round(percent)}%`;
        this.uploadedSize.textContent = this.formatFileSize(uploaded);
        this.totalSize.textContent = this.formatFileSize(total);
        
        // Calculate speed and time remaining
        if (this.uploadProgress.startTime) {
            const elapsed = (Date.now() - this.uploadProgress.startTime) / 1000;
            const speed = uploaded / elapsed;
            const remaining = (total - uploaded) / speed;
            
            this.uploadSpeed.textContent = this.formatFileSize(speed) + '/s';
            this.timeRemaining.textContent = remaining > 0 ? this.formatTime(remaining) : 'Complete';
        }
    }
    
    async cancelUpload() {
        if (!this.uploadSession) return;
        
        try {
            await fetch(`/api/video/upload/${this.uploadSession.session_id}`, {
                method: 'DELETE'
            });
        } catch (error) {
            console.error('Cancel upload error:', error);
        }
        
        this.resetForm();
    }
    
    resetForm() {
        // Reset form
        this.form.reset();
        this.form.style.display = 'block';
        
        // Reset state
        this.currentFile = null;
        this.uploadSession = null;
        this.tags = [];
        this.uploadProgress = { percent: 0, uploadedSize: 0, totalSize: 0, speed: 0, startTime: null };
        
        // Hide sections
        this.fileInfo.style.display = 'none';
        this.qualitySection.style.display = 'none';
        this.thumbnailSection.style.display = 'none';
        this.progressSection.style.display = 'none';
        this.uploadResult.style.display = 'none';
        
        // Reset buttons
        this.analyzeButton.disabled = true;
        this.uploadButton.disabled = true;
        this.uploadButton.textContent = 'Upload Video';
        this.uploadButton.style.display = 'inline-block';
        this.cancelButton.style.display = 'none';
        
        // Clear tags
        this.updateTagsDisplay();
        
        // Clear counters
        this.updateCharCounter('title');
        this.updateCharCounter('description');
    }
    
    // Tag management
    handleTagsInput(event) {
        if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault();
            this.addTagFromInput();
        }
    }
    
    addTagFromInput() {
        const tagText = this.tagsInput.value.trim();
        if (tagText) {
            this.addTag(tagText);
            this.tagsInput.value = '';
        }
    }
    
    addTag(tagText) {
        const normalizedTag = this.normalizeTag(tagText);
        if (normalizedTag && !this.tags.includes(normalizedTag) && this.tags.length < 20) {
            this.tags.push(normalizedTag);
            this.updateTagsDisplay();
        }
    }
    
    removeTag(tag) {
        const index = this.tags.indexOf(tag);
        if (index > -1) {
            this.tags.splice(index, 1);
            this.updateTagsDisplay();
        }
    }
    
    normalizeTag(tag) {
        return tag.toLowerCase().replace(/[^\w\-_]/g, '').substring(0, 30);
    }
    
    updateTagsDisplay() {
        this.tagsContainer.innerHTML = '';
        
        this.tags.forEach(tag => {
            const tagElement = document.createElement('div');
            tagElement.className = 'tag-item';
            tagElement.innerHTML = `
                ${tag}
                <button type="button" class="tag-remove" onclick="videoUpload.removeTag('${tag}')">&times;</button>
            `;
            this.tagsContainer.appendChild(tagElement);
        });
    }
    
    // Popular tags modal
    async loadPopularTags() {
        try {
            const response = await fetch('/api/video/metadata/tags/popular');
            if (response.ok) {
                this.popularTags = await response.json();
            }
        } catch (error) {
            console.error('Failed to load popular tags:', error);
        }
    }
    
    showPopularTagsModal() {
        this.popularTagsList.innerHTML = '';
        
        this.popularTags.forEach(tagSuggestion => {
            const tagElement = document.createElement('div');
            tagElement.className = 'tag-suggestion';
            tagElement.textContent = `${tagSuggestion.tag} (${tagSuggestion.usage_count})`;
            tagElement.addEventListener('click', () => {
                this.addTag(tagSuggestion.tag);
                tagElement.classList.add('selected');
            });
            this.popularTagsList.appendChild(tagElement);
        });
        
        this.popularTagsModal.style.display = 'flex';
    }
    
    hidePopularTagsModal() {
        this.popularTagsModal.style.display = 'none';
    }
    
    // Thumbnail management
    async loadVideoThumbnails(videoId) {
        try {
            const response = await fetch(`/api/video/thumbnails/videos/${videoId}`);
            if (response.ok) {
                const thumbnails = await response.json();
                this.displayThumbnails(thumbnails);
            } else {
                // Generate thumbnails if none exist
                await this.generateDefaultThumbnails(videoId);
            }
        } catch (error) {
            console.error('Failed to load thumbnails:', error);
            this.showError('Failed to load thumbnails');
        }
    }
    
    async generateDefaultThumbnails(videoId) {
        try {
            const response = await fetch(`/api/video/thumbnails/videos/${videoId}/regenerate-defaults`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.displayThumbnails(result.thumbnails);
            } else {
                throw new Error('Failed to generate thumbnails');
            }
        } catch (error) {
            console.error('Failed to generate thumbnails:', error);
            this.showThumbnailError();
        }
    }
    
    displayThumbnails(thumbnails) {
        this.thumbnailGrid.innerHTML = '';
        
        if (!thumbnails || thumbnails.length === 0) {
            this.showThumbnailError('No thumbnails available');
            return;
        }
        
        thumbnails.forEach(thumbnail => {
            const thumbnailElement = document.createElement('div');
            thumbnailElement.className = `thumbnail-item ${thumbnail.is_selected ? 'selected' : ''}`;
            thumbnailElement.addEventListener('click', () => this.selectThumbnail(thumbnail));
            
            thumbnailElement.innerHTML = `
                <img src="${thumbnail.url}" alt="Thumbnail at ${thumbnail.timestamp}s" class="thumbnail-image">
                <div class="thumbnail-timestamp">${this.formatTime(thumbnail.timestamp)}</div>
                <div class="thumbnail-info">
                    ${(thumbnail.file_size / 1024).toFixed(1)} KB
                </div>
            `;
            
            this.thumbnailGrid.appendChild(thumbnailElement);
        });
    }
    
    async selectThumbnail(thumbnail) {
        try {
            const videoId = this.resultVideoId.textContent;
            const response = await fetch(`/api/video/thumbnails/videos/${videoId}/select`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    selected_timestamp: thumbnail.timestamp
                })
            });
            
            if (response.ok) {
                // Update UI to show selection
                document.querySelectorAll('.thumbnail-item').forEach(item => {
                    item.classList.remove('selected');
                });
                
                event.currentTarget.classList.add('selected');
                this.showSuccess('Thumbnail selected successfully');
            } else {
                throw new Error('Failed to select thumbnail');
            }
        } catch (error) {
            console.error('Failed to select thumbnail:', error);
            this.showError('Failed to select thumbnail');
        }
    }
    
    async regenerateThumbnails() {
        try {
            const videoId = this.resultVideoId.textContent;
            
            // Show loading state
            this.thumbnailGrid.innerHTML = '<div class="thumbnail-loading">Generating thumbnails...</div>';
            
            const response = await fetch(`/api/video/thumbnails/videos/${videoId}/regenerate-defaults`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.displayThumbnails(result.thumbnails);
                this.showSuccess('Thumbnails regenerated successfully');
            } else {
                throw new Error('Failed to regenerate thumbnails');
            }
        } catch (error) {
            console.error('Failed to regenerate thumbnails:', error);
            this.showThumbnailError('Failed to regenerate thumbnails');
        }
    }
    
    async autoSelectThumbnail() {
        try {
            const videoId = this.resultVideoId.textContent;
            
            const response = await fetch(`/api/video/thumbnails/videos/${videoId}/auto-select`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const selectedThumbnail = await response.json();
                
                // Update UI to show selection
                document.querySelectorAll('.thumbnail-item').forEach(item => {
                    item.classList.remove('selected');
                });
                
                // Find and select the corresponding thumbnail element
                const thumbnailElements = document.querySelectorAll('.thumbnail-item');
                thumbnailElements.forEach(element => {
                    const timestampText = element.querySelector('.thumbnail-timestamp').textContent;
                    const timestamp = this.parseTimeToSeconds(timestampText);
                    
                    if (Math.abs(timestamp - selectedThumbnail.timestamp) < 0.1) {
                        element.classList.add('selected');
                    }
                });
                
                this.showSuccess('Best thumbnail selected automatically');
            } else {
                throw new Error('Failed to auto-select thumbnail');
            }
        } catch (error) {
            console.error('Failed to auto-select thumbnail:', error);
            this.showError('Failed to auto-select thumbnail');
        }
    }
    
    showThumbnailError(message = 'Failed to load thumbnails') {
        this.thumbnailGrid.innerHTML = `<div class="thumbnail-error">${message}</div>`;
    }
    
    parseTimeToSeconds(timeStr) {
        // Parse time format like "1m 30s" or "45s"
        const parts = timeStr.split(' ');
        let seconds = 0;
        
        for (const part of parts) {
            if (part.includes('m')) {
                seconds += parseInt(part) * 60;
            } else if (part.includes('s')) {
                seconds += parseInt(part);
            }
        }
        
        return seconds;
    }
    
    // Character counters
    updateCharCounter(field) {
        const input = field === 'title' ? this.titleInput : this.descriptionInput;
        const counter = field === 'title' ? this.titleCounter : this.descriptionCounter;
        const maxLength = field === 'title' ? 100 : 5000;
        
        const currentLength = input.value.length;
        counter.textContent = currentLength;
        
        // Update color based on usage
        if (currentLength > maxLength * 0.9) {
            counter.style.color = '#dc3545';
        } else if (currentLength > maxLength * 0.7) {
            counter.style.color = '#ffc107';
        } else {
            counter.style.color = '#6c757d';
        }
    }
    
    // Utility functions
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    formatTime(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.round(seconds % 60);
        return `${minutes}m ${remainingSeconds}s`;
    }
    
    showError(message) {
        // Simple error display - could be enhanced with a proper notification system
        alert(`Error: ${message}`);
    }
    
    showSuccess(message) {
        // Simple success display - could be enhanced with a proper notification system
        console.log(`Success: ${message}`);
    }
    
    showFieldError(field, message) {
        const input = field === 'title' ? this.titleInput : this.descriptionInput;
        const group = input.closest('.form-group');
        
        group.classList.add('error');
        
        let errorElement = group.querySelector('.error-message');
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'error-message';
            group.appendChild(errorElement);
        }
        errorElement.textContent = message;
    }
    
    clearFieldError(field) {
        const input = field === 'title' ? this.titleInput : this.descriptionInput;
        const group = input.closest('.form-group');
        
        group.classList.remove('error');
        const errorElement = group.querySelector('.error-message');
        if (errorElement) {
            errorElement.remove();
        }
    }
}

// Initialize when DOM is loaded
let videoUpload;
document.addEventListener('DOMContentLoaded', () => {
    videoUpload = new VideoUploadManager();
});