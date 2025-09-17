/**
 * Adaptive Video Player with HLS.js integration
 * Supports adaptive streaming, quality selection, and viewing session tracking
 */

class AdaptiveVideoPlayer {
    constructor() {
        this.video = null;
        this.hls = null;
        this.currentVideoId = null;
        this.sessionToken = null;
        this.viewingSession = null;
        this.qualityLevels = [];
        this.currentQuality = 'auto';
        this.playbackSpeed = 1;
        this.stats = {
            qualitySwitches: 0,
            bufferingEvents: 0,
            droppedFrames: 0,
            bandwidth: 0
        };
        this.progressUpdateInterval = null;
        this.statsUpdateInterval = null;
        
        this.init();
    }
    
    init() {
        this.video = document.getElementById('adaptive-video-player');
        if (!this.video) {
            console.error('Video element not found');
            return;
        }
        
        this.setupEventListeners();
        this.setupUI();
        
        // Check HLS support
        if (!Hls.isSupported()) {
            console.warn('HLS not supported, falling back to native video');
            this.showError('Your browser does not support adaptive streaming');
        }
    }
    
    setupEventListeners() {
        // Video events
        this.video.addEventListener('loadstart', () => this.onLoadStart());
        this.video.addEventListener('loadedmetadata', () => this.onLoadedMetadata());
        this.video.addEventListener('canplay', () => this.onCanPlay());
        this.video.addEventListener('play', () => this.onPlay());
        this.video.addEventListener('pause', () => this.onPause());
        this.video.addEventListener('ended', () => this.onEnded());
        this.video.addEventListener('error', (e) => this.onError(e));
        this.video.addEventListener('waiting', () => this.onBuffering());
        this.video.addEventListener('playing', () => this.onPlaying());
        this.video.addEventListener('timeupdate', () => this.onTimeUpdate());
        
        // Quality selector
        const qualityButton = document.getElementById('quality-button');
        const qualityMenu = document.getElementById('quality-menu');
        
        qualityButton?.addEventListener('click', () => {
            qualityMenu.style.display = qualityMenu.style.display === 'block' ? 'none' : 'block';
        });
        
        // Speed selector
        const speedButton = document.getElementById('speed-button');
        const speedMenu = document.getElementById('speed-menu');
        
        speedButton?.addEventListener('click', () => {
            speedMenu.style.display = speedMenu.style.display === 'block' ? 'none' : 'block';
        });
        
        // Speed options
        document.querySelectorAll('.speed-option').forEach(option => {
            option.addEventListener('click', (e) => {
                const speed = parseFloat(e.target.dataset.speed);
                this.setPlaybackSpeed(speed);
            });
        });
        
        // Retry button
        const retryButton = document.getElementById('retry-button');
        retryButton?.addEventListener('click', () => this.retry());
        
        // Close menus when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.quality-selector')) {
                qualityMenu.style.display = 'none';
            }
            if (!e.target.closest('.speed-selector')) {
                speedMenu.style.display = 'none';
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        
        // Visibility change (for pausing when tab is hidden)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && !this.video.paused) {
                this.pauseForVisibility = true;
                this.video.pause();
            } else if (!document.hidden && this.pauseForVisibility) {
                this.pauseForVisibility = false;
                this.video.play();
            }
        });
        
        // Like/Dislike buttons
        const likeButton = document.getElementById('like-button');
        const dislikeButton = document.getElementById('dislike-button');
        
        likeButton?.addEventListener('click', () => this.likeVideo());
        dislikeButton?.addEventListener('click', () => this.dislikeVideo());
        
        // Comments functionality
        this.setupCommentsEventListeners();
        
        // Page unload handling
        window.addEventListener('beforeunload', () => {
            // Send final progress update synchronously
            if (this.sessionToken && this.currentVideoId) {
                const currentTime = Math.floor(this.video.currentTime);
                const duration = Math.floor(this.video.duration) || 0;
                const completionPercentage = duration > 0 ? Math.floor((currentTime / duration) * 100) : 0;
                
                const finalData = {
                    current_position_seconds: currentTime,
                    completion_percentage: completionPercentage,
                    quality_switches: this.stats.qualitySwitches,
                    buffering_events: this.stats.bufferingEvents
                };
                
                // Use sendBeacon for reliable delivery
                navigator.sendBeacon(
                    `/api/streaming/videos/${this.currentVideoId}/sessions/${this.sessionToken}/end`,
                    JSON.stringify(finalData)
                );
            }
        });
    }
    
    setupUI() {
        // Initialize stats display
        this.updateStats();
        
        // Start stats update interval
        this.statsUpdateInterval = setInterval(() => {
            this.updateStats();
        }, 1000);
    }
    
    async loadVideo(videoId, userId = null) {
        try {
            this.currentVideoId = videoId;
            this.userId = userId;
            this.showLoading();
            
            // Check for resume position if user is logged in
            let resumePosition = 0;
            if (userId) {
                const resumeData = await this.getResumePosition(videoId, userId);
                if (resumeData.has_resume_position) {
                    resumePosition = resumeData.resume_position;
                    
                    // Show resume dialog
                    const shouldResume = await this.showResumeDialog(resumePosition);
                    if (!shouldResume) {
                        resumePosition = 0;
                    }
                }
            }
            
            // Create viewing session
            await this.createViewingSession(videoId, userId);
            
            // Get video manifest
            const manifest = await this.getVideoManifest(videoId, userId);
            
            // Update video info
            this.updateVideoInfo(manifest);
            
            // Load HLS stream
            await this.loadHLSStream(manifest.master_playlist_url);
            
            // Set resume position if applicable
            if (resumePosition > 0) {
                this.video.addEventListener('loadedmetadata', () => {
                    this.video.currentTime = resumePosition;
                }, { once: true });
            }
            
            // Get quality recommendation
            await this.getQualityRecommendation(videoId);
            
            // Load like/dislike status
            await this.loadLikeStatus();
            
            // Load comments
            await this.loadComments();
            
        } catch (error) {
            console.error('Failed to load video:', error);
            this.showError('Failed to load video: ' + error.message);
        }
    }
    
    async createViewingSession(videoId, userId = null) {
        try {
            const response = await fetch(`/api/streaming/videos/${videoId}/sessions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ user_id: userId })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.viewingSession = await response.json();
            this.sessionToken = this.viewingSession.session_token;
            
            // Start progress tracking
            this.startProgressTracking();
            
        } catch (error) {
            console.warn('Failed to create viewing session:', error);
            // Continue without session tracking
        }
    }
    
    async getVideoManifest(videoId, userId = null) {
        const params = new URLSearchParams();
        if (userId) params.append('user_id', userId);
        if (this.sessionToken) params.append('session_token', this.sessionToken);
        
        const response = await fetch(`/api/streaming/videos/${videoId}/manifest?${params}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }
    
    async getQualityRecommendation(videoId) {
        try {
            // Detect bandwidth
            const bandwidth = await this.detectBandwidth();
            const deviceType = this.detectDeviceType();
            
            const params = new URLSearchParams({
                bandwidth_kbps: bandwidth.toString(),
                device_type: deviceType
            });
            
            const response = await fetch(`/api/streaming/videos/${videoId}/recommendation?${params}`);
            
            if (response.ok) {
                const recommendation = await response.json();
                this.applyQualityRecommendation(recommendation.recommendation);
            }
        } catch (error) {
            console.warn('Failed to get quality recommendation:', error);
        }
    }
    
    async detectBandwidth() {
        try {
            const startTime = performance.now();
            const response = await fetch('/api/streaming/bandwidth-test?test_size_kb=100');
            const endTime = performance.now();
            
            if (response.ok) {
                const data = await response.json();
                const durationMs = endTime - startTime;
                const durationSeconds = durationMs / 1000;
                const bytesPerSecond = data.test_size_bytes / durationSeconds;
                const kbps = (bytesPerSecond * 8) / 1000;
                
                this.stats.bandwidth = Math.round(kbps);
                return kbps;
            }
        } catch (error) {
            console.warn('Bandwidth detection failed:', error);
        }
        
        return 2000; // Default to 2 Mbps
    }
    
    detectDeviceType() {
        const userAgent = navigator.userAgent.toLowerCase();
        const screenWidth = window.screen.width;
        
        if (/mobile|android|iphone|ipod|blackberry|iemobile|opera mini/.test(userAgent)) {
            return 'mobile';
        } else if (/tablet|ipad/.test(userAgent) || (screenWidth >= 768 && screenWidth <= 1024)) {
            return 'tablet';
        } else {
            return 'desktop';
        }
    }
    
    async loadHLSStream(manifestUrl) {
        if (Hls.isSupported()) {
            this.hls = new Hls({
                enableWorker: true,
                lowLatencyMode: false,
                backBufferLength: 90
            });
            
            this.hls.loadSource(manifestUrl);
            this.hls.attachMedia(this.video);
            
            // HLS events
            this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
                this.onManifestParsed();
            });
            
            this.hls.on(Hls.Events.LEVEL_SWITCHED, (event, data) => {
                this.onQualitySwitch(data);
            });
            
            this.hls.on(Hls.Events.ERROR, (event, data) => {
                this.onHLSError(event, data);
            });
            
            this.hls.on(Hls.Events.FRAG_BUFFERED, (event, data) => {
                this.onFragmentBuffered(data);
            });
            
        } else if (this.video.canPlayType('application/vnd.apple.mpegurl')) {
            // Native HLS support (Safari)
            this.video.src = manifestUrl;
        } else {
            throw new Error('HLS not supported');
        }
    }
    
    onManifestParsed() {
        this.hideLoading();
        
        if (this.hls) {
            this.qualityLevels = this.hls.levels.map((level, index) => ({
                index: index,
                height: level.height,
                width: level.width,
                bitrate: level.bitrate,
                name: `${level.height}p`
            }));
            
            this.updateQualitySelector();
        }
    }
    
    onQualitySwitch(data) {
        this.stats.qualitySwitches++;
        
        if (this.hls && this.hls.levels[data.level]) {
            const level = this.hls.levels[data.level];
            document.getElementById('stat-quality').textContent = `${level.height}p`;
        }
    }
    
    onHLSError(event, data) {
        console.error('HLS Error:', data);
        
        if (data.fatal) {
            switch (data.type) {
                case Hls.ErrorTypes.NETWORK_ERROR:
                    this.hls.startLoad();
                    break;
                case Hls.ErrorTypes.MEDIA_ERROR:
                    this.hls.recoverMediaError();
                    break;
                default:
                    this.showError('Fatal HLS error: ' + data.details);
                    break;
            }
        }
    }
    
    onFragmentBuffered(data) {
        // Update buffer health
        if (this.video.buffered.length > 0) {
            const currentTime = this.video.currentTime;
            const bufferedEnd = this.video.buffered.end(this.video.buffered.length - 1);
            const bufferHealth = Math.max(0, bufferedEnd - currentTime);
            
            document.getElementById('stat-buffer').textContent = `${bufferHealth.toFixed(1)}s`;
        }
    }
    
    updateQualitySelector() {
        const qualityMenu = document.getElementById('quality-menu');
        if (!qualityMenu) return;
        
        // Clear existing options (except auto)
        const autoOption = qualityMenu.querySelector('[data-quality="auto"]');
        qualityMenu.innerHTML = '';
        qualityMenu.appendChild(autoOption);
        
        // Add quality options
        this.qualityLevels.forEach((level, index) => {
            const option = document.createElement('div');
            option.className = 'quality-option';
            option.dataset.quality = index.toString();
            option.innerHTML = `
                <span>${level.name}</span>
                <span class="quality-indicator"></span>
            `;
            
            option.addEventListener('click', () => {
                this.setQuality(index);
            });
            
            qualityMenu.appendChild(option);
        });
    }
    
    setQuality(levelIndex) {
        if (!this.hls) return;
        
        if (levelIndex === 'auto' || levelIndex === -1) {
            this.hls.currentLevel = -1; // Auto
            this.currentQuality = 'auto';
            document.getElementById('current-quality').textContent = 'Auto';
        } else {
            this.hls.currentLevel = levelIndex;
            this.currentQuality = levelIndex;
            const level = this.qualityLevels[levelIndex];
            document.getElementById('current-quality').textContent = level.name;
        }
        
        // Update UI
        document.querySelectorAll('.quality-option').forEach(option => {
            option.classList.remove('selected');
        });
        
        const selectedOption = document.querySelector(`[data-quality="${levelIndex}"]`);
        if (selectedOption) {
            selectedOption.classList.add('selected');
        }
        
        // Hide menu
        document.getElementById('quality-menu').style.display = 'none';
    }
    
    setPlaybackSpeed(speed) {
        this.video.playbackRate = speed;
        this.playbackSpeed = speed;
        
        document.getElementById('current-speed').textContent = `${speed}x`;
        
        // Update UI
        document.querySelectorAll('.speed-option').forEach(option => {
            option.classList.remove('selected');
        });
        
        const selectedOption = document.querySelector(`[data-speed="${speed}"]`);
        if (selectedOption) {
            selectedOption.classList.add('selected');
        }
        
        // Hide menu
        document.getElementById('speed-menu').style.display = 'none';
    }
    
    applyQualityRecommendation(recommendation) {
        if (!recommendation.recommended) return;
        
        const recommendedQuality = recommendation.recommended;
        const targetHeight = recommendedQuality.height;
        
        // Find matching quality level
        const matchingLevel = this.qualityLevels.findIndex(level => level.height === targetHeight);
        
        if (matchingLevel !== -1) {
            this.setQuality(matchingLevel);
        }
    }
    
    startProgressTracking() {
        if (!this.sessionToken) return;
        
        this.progressUpdateInterval = setInterval(async () => {
            if (this.video.paused || this.video.ended) return;
            
            try {
                await this.updateViewingProgress();
            } catch (error) {
                console.warn('Failed to update viewing progress:', error);
            }
        }, 10000); // Update every 10 seconds
    }
    
    async getResumePosition(videoId, userId) {
        try {
            const response = await fetch(`/api/streaming/videos/${videoId}/resume-position?user_id=${userId}`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.warn('Failed to get resume position:', error);
        }
        
        return {
            has_resume_position: false,
            resume_position: 0,
            completion_percentage: 0
        };
    }
    
    async showResumeDialog(resumePosition) {
        return new Promise((resolve) => {
            const formattedTime = this.formatDuration(resumePosition);
            
            // Create resume dialog
            const dialog = document.createElement('div');
            dialog.className = 'resume-dialog';
            dialog.innerHTML = `
                <div class="resume-dialog-content">
                    <h3>Resume Playback</h3>
                    <p>You were watching this video. Resume from ${formattedTime}?</p>
                    <div class="resume-dialog-buttons">
                        <button id="resume-yes" class="resume-button primary">Resume</button>
                        <button id="resume-no" class="resume-button secondary">Start Over</button>
                    </div>
                </div>
            `;
            
            // Add styles
            dialog.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
            `;
            
            const content = dialog.querySelector('.resume-dialog-content');
            content.style.cssText = `
                background: var(--surface-color);
                padding: 30px;
                border-radius: 8px;
                text-align: center;
                max-width: 400px;
                border: 1px solid var(--border-color);
            `;
            
            const buttons = dialog.querySelector('.resume-dialog-buttons');
            buttons.style.cssText = `
                display: flex;
                gap: 15px;
                justify-content: center;
                margin-top: 20px;
            `;
            
            const resumeButtons = dialog.querySelectorAll('.resume-button');
            resumeButtons.forEach(button => {
                button.style.cssText = `
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 1rem;
                    transition: background-color 0.2s;
                `;
            });
            
            const primaryButton = dialog.querySelector('.primary');
            primaryButton.style.cssText += `
                background: var(--primary-color);
                color: var(--secondary-color);
            `;
            
            const secondaryButton = dialog.querySelector('.secondary');
            secondaryButton.style.cssText += `
                background: var(--border-color);
                color: var(--text-color);
            `;
            
            document.body.appendChild(dialog);
            
            // Handle button clicks
            dialog.querySelector('#resume-yes').addEventListener('click', () => {
                document.body.removeChild(dialog);
                resolve(true);
            });
            
            dialog.querySelector('#resume-no').addEventListener('click', () => {
                document.body.removeChild(dialog);
                resolve(false);
            });
            
            // Auto-resume after 10 seconds
            setTimeout(() => {
                if (document.body.contains(dialog)) {
                    document.body.removeChild(dialog);
                    resolve(true);
                }
            }, 10000);
        });
    }
    
    async updateViewingProgress() {
        if (!this.sessionToken || !this.currentVideoId) return;
        
        const currentTime = Math.floor(this.video.currentTime);
        const duration = Math.floor(this.video.duration) || 0;
        const completionPercentage = duration > 0 ? Math.floor((currentTime / duration) * 100) : 0;
        
        const progressData = {
            session_token: this.sessionToken,
            current_position_seconds: currentTime,
            completion_percentage: completionPercentage,
            quality_switches: this.stats.qualitySwitches,
            buffering_events: this.stats.bufferingEvents
        };
        
        try {
            await fetch(`/api/streaming/videos/${this.currentVideoId}/progress`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(progressData)
            });
        } catch (error) {
            console.warn('Failed to update viewing progress:', error);
        }
    }
    
    async endViewingSession() {
        if (!this.sessionToken || !this.currentVideoId) return;
        
        const currentTime = Math.floor(this.video.currentTime);
        const duration = Math.floor(this.video.duration) || 0;
        const completionPercentage = duration > 0 ? Math.floor((currentTime / duration) * 100) : 0;
        
        const finalData = {
            current_position_seconds: currentTime,
            completion_percentage: completionPercentage,
            quality_switches: this.stats.qualitySwitches,
            buffering_events: this.stats.bufferingEvents
        };
        
        try {
            await fetch(`/api/streaming/videos/${this.currentVideoId}/sessions/${this.sessionToken}/end`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(finalData)
            });
        } catch (error) {
            console.warn('Failed to end viewing session:', error);
        }
    }
    
    updateVideoInfo(manifest) {
        document.getElementById('video-title').textContent = manifest.title || 'Untitled Video';
        document.getElementById('video-description-text').textContent = manifest.description || 'No description available';
        
        if (manifest.duration) {
            document.getElementById('video-duration').textContent = this.formatDuration(manifest.duration);
        }
    }
    
    updateStats() {
        // Update bandwidth display
        document.getElementById('stat-bandwidth').textContent = 
            this.stats.bandwidth > 0 ? `${this.stats.bandwidth} kbps` : '--';
        
        // Update counters
        document.getElementById('stat-switches').textContent = this.stats.qualitySwitches;
        document.getElementById('stat-buffering').textContent = this.stats.bufferingEvents;
        document.getElementById('stat-dropped').textContent = this.stats.droppedFrames;
        
        // Update dropped frames if available
        if (this.video.getVideoPlaybackQuality) {
            const quality = this.video.getVideoPlaybackQuality();
            this.stats.droppedFrames = quality.droppedVideoFrames;
            document.getElementById('stat-dropped').textContent = quality.droppedVideoFrames;
        }
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
    
    handleKeyboard(event) {
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return; // Don't handle shortcuts when typing
        }
        
        switch (event.code) {
            case 'Space':
                event.preventDefault();
                this.video.paused ? this.video.play() : this.video.pause();
                break;
            case 'ArrowLeft':
                event.preventDefault();
                this.video.currentTime = Math.max(0, this.video.currentTime - 10);
                break;
            case 'ArrowRight':
                event.preventDefault();
                this.video.currentTime = Math.min(this.video.duration, this.video.currentTime + 10);
                break;
            case 'ArrowUp':
                event.preventDefault();
                this.video.volume = Math.min(1, this.video.volume + 0.1);
                break;
            case 'ArrowDown':
                event.preventDefault();
                this.video.volume = Math.max(0, this.video.volume - 0.1);
                break;
            case 'KeyM':
                event.preventDefault();
                this.video.muted = !this.video.muted;
                break;
            case 'KeyF':
                event.preventDefault();
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else {
                    this.video.requestFullscreen();
                }
                break;
        }
    }
    
    // Event handlers
    onLoadStart() {
        this.showLoading();
    }
    
    onLoadedMetadata() {
        // Video metadata loaded
    }
    
    onCanPlay() {
        this.hideLoading();
    }
    
    onPlay() {
        // Video started playing
    }
    
    onPause() {
        // Video paused
    }
    
    onEnded() {
        // Video ended
        if (this.progressUpdateInterval) {
            clearInterval(this.progressUpdateInterval);
        }
        
        // End viewing session
        this.endViewingSession();
    }
    
    onError(event) {
        console.error('Video error:', event);
        this.showError('Video playback error');
    }
    
    onBuffering() {
        this.stats.bufferingEvents++;
    }
    
    onPlaying() {
        // Video resumed playing after buffering
    }
    
    onTimeUpdate() {
        // Update progress bar or other time-dependent UI
    }
    
    // UI methods
    showLoading() {
        document.getElementById('loading-overlay').style.display = 'flex';
        document.getElementById('error-overlay').style.display = 'none';
    }
    
    hideLoading() {
        document.getElementById('loading-overlay').style.display = 'none';
    }
    
    showError(message) {
        document.getElementById('loading-overlay').style.display = 'none';
        document.getElementById('error-overlay').style.display = 'flex';
        document.querySelector('.error-message').textContent = message;
    }
    
    hideError() {
        document.getElementById('error-overlay').style.display = 'none';
    }
    
    retry() {
        this.hideError();
        if (this.currentVideoId) {
            this.loadVideo(this.currentVideoId);
        }
    }
    
    // Like/Dislike functionality
    async loadLikeStatus() {
        if (!this.currentVideoId) return;
        
        try {
            // Load like counts
            const countsResponse = await fetch(`/api/videos/${this.currentVideoId}/likes`);
            if (countsResponse.ok) {
                const counts = await countsResponse.json();
                this.updateLikeCounts(counts.like_count, counts.dislike_count);
            }
            
            // Load user's like status if logged in
            if (this.userId) {
                const statusResponse = await fetch(`/api/videos/${this.currentVideoId}/user-like`);
                if (statusResponse.ok) {
                    const status = await statusResponse.json();
                    this.updateUserLikeStatus(status.user_status);
                }
            }
        } catch (error) {
            console.warn('Failed to load like status:', error);
        }
    }
    
    async likeVideo() {
        if (!this.currentVideoId) return;
        
        try {
            const response = await fetch(`/api/videos/${this.currentVideoId}/like`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                this.updateLikeCounts(result.like_count, result.dislike_count);
                this.updateUserLikeStatus(result.user_status);
            } else if (response.status === 401) {
                this.showLoginPrompt();
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to like video:', error);
            this.showError('Failed to like video. Please try again.');
        }
    }
    
    async dislikeVideo() {
        if (!this.currentVideoId) return;
        
        try {
            const response = await fetch(`/api/videos/${this.currentVideoId}/dislike`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                this.updateLikeCounts(result.like_count, result.dislike_count);
                this.updateUserLikeStatus(result.user_status);
            } else if (response.status === 401) {
                this.showLoginPrompt();
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to dislike video:', error);
            this.showError('Failed to dislike video. Please try again.');
        }
    }
    
    updateLikeCounts(likeCount, dislikeCount) {
        const likeCountElement = document.getElementById('like-count');
        const dislikeCountElement = document.getElementById('dislike-count');
        
        if (likeCountElement) {
            likeCountElement.textContent = this.formatCount(likeCount);
        }
        
        if (dislikeCountElement) {
            dislikeCountElement.textContent = this.formatCount(dislikeCount);
        }
    }
    
    updateUserLikeStatus(status) {
        const likeButton = document.getElementById('like-button');
        const dislikeButton = document.getElementById('dislike-button');
        
        if (!likeButton || !dislikeButton) return;
        
        // Reset button states
        likeButton.classList.remove('active');
        dislikeButton.classList.remove('active');
        
        // Set active state based on user status
        if (status === 'liked') {
            likeButton.classList.add('active');
        } else if (status === 'disliked') {
            dislikeButton.classList.add('active');
        }
    }
    
    formatCount(count) {
        if (count >= 1000000) {
            return (count / 1000000).toFixed(1) + 'M';
        } else if (count >= 1000) {
            return (count / 1000).toFixed(1) + 'K';
        } else {
            return count.toString();
        }
    }
    
    showLoginPrompt() {
        // Create login prompt dialog
        const dialog = document.createElement('div');
        dialog.className = 'login-prompt-dialog';
        dialog.innerHTML = `
            <div class="login-prompt-content">
                <h3>Sign In Required</h3>
                <p>You need to be signed in to like or dislike videos.</p>
                <div class="login-prompt-buttons">
                    <button id="login-close" class="login-button secondary">Close</button>
                    <button id="login-signin" class="login-button primary">Sign In</button>
                </div>
            </div>
        `;
        
        // Add styles
        dialog.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        `;
        
        const content = dialog.querySelector('.login-prompt-content');
        content.style.cssText = `
            background: var(--surface-color);
            padding: 30px;
            border-radius: 8px;
            text-align: center;
            max-width: 400px;
            border: 1px solid var(--border-color);
        `;
        
        const buttons = dialog.querySelector('.login-prompt-buttons');
        buttons.style.cssText = `
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 20px;
        `;
        
        const loginButtons = dialog.querySelectorAll('.login-button');
        loginButtons.forEach(button => {
            button.style.cssText = `
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 1rem;
                transition: background-color 0.2s;
            `;
        });
        
        const primaryButton = dialog.querySelector('.primary');
        primaryButton.style.cssText += `
            background: var(--primary-color);
            color: var(--secondary-color);
        `;
        
        const secondaryButton = dialog.querySelector('.secondary');
        secondaryButton.style.cssText += `
            background: var(--border-color);
            color: var(--text-color);
        `;
        
        document.body.appendChild(dialog);
        
        // Handle button clicks
        dialog.querySelector('#login-close').addEventListener('click', () => {
            document.body.removeChild(dialog);
        });
        
        dialog.querySelector('#login-signin').addEventListener('click', () => {
            // Redirect to login page or open login modal
            window.location.href = '/auth/login';
        });
        
        // Auto-close after 5 seconds
        setTimeout(() => {
            if (document.body.contains(dialog)) {
                document.body.removeChild(dialog);
            }
        }, 5000);
    }
    
    // Comments functionality
    setupCommentsEventListeners() {
        // Comment form
        const commentForm = document.getElementById('comment-form');
        const commentInput = document.getElementById('comment-input');
        const commentSubmit = document.getElementById('comment-submit');
        const commentCancel = document.getElementById('comment-cancel');
        const commentsSort = document.getElementById('comments-sort-select');
        const loadMoreButton = document.getElementById('load-more-comments');
        
        // Enable/disable submit button based on input
        commentInput?.addEventListener('input', () => {
            const hasContent = commentInput.value.trim().length > 0;
            commentSubmit.disabled = !hasContent;
        });
        
        // Focus/blur events for comment form
        commentInput?.addEventListener('focus', () => {
            document.querySelector('.comment-form-actions').style.display = 'flex';
        });
        
        commentCancel?.addEventListener('click', () => {
            commentInput.value = '';
            commentSubmit.disabled = true;
            document.querySelector('.comment-form-actions').style.display = 'none';
        });
        
        // Submit comment
        commentForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitComment();
        });
        
        // Sort change
        commentsSort?.addEventListener('change', () => {
            this.loadComments(1, commentsSort.value);
        });
        
        // Load more comments
        loadMoreButton?.addEventListener('click', () => {
            this.loadMoreComments();
        });
    }
    
    async loadComments(page = 1, sort = 'newest') {
        if (!this.currentVideoId) return;
        
        try {
            const response = await fetch(
                `/api/videos/${this.currentVideoId}/comments?page=${page}&limit=20&sort=${sort}`
            );
            
            if (response.ok) {
                const data = await response.json();
                
                if (page === 1) {
                    this.renderComments(data.comments);
                    this.updateCommentsTitle(data.pagination.total);
                } else {
                    this.appendComments(data.comments);
                }
                
                this.updateLoadMoreButton(data.pagination);
                this.currentCommentsPage = page;
                this.currentCommentsSort = sort;
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to load comments:', error);
            this.showCommentsError('Failed to load comments');
        }
    }
    
    async submitComment(parentCommentId = null) {
        if (!this.currentVideoId) return;
        
        const commentInput = document.getElementById('comment-input');
        const content = commentInput.value.trim();
        
        if (!content) return;
        
        try {
            const response = await fetch(`/api/videos/${this.currentVideoId}/comments`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: content,
                    parent_comment_id: parentCommentId
                })
            });
            
            if (response.ok) {
                const comment = await response.json();
                
                if (parentCommentId) {
                    this.addReplyToComment(parentCommentId, comment);
                } else {
                    this.prependComment(comment);
                }
                
                // Clear form
                commentInput.value = '';
                document.getElementById('comment-submit').disabled = true;
                document.querySelector('.comment-form-actions').style.display = 'none';
                
                // Update comments count
                this.incrementCommentsCount();
                
            } else if (response.status === 401) {
                this.showLoginPrompt();
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to submit comment:', error);
            this.showError('Failed to submit comment. Please try again.');
        }
    }
    
    renderComments(comments) {
        const commentsList = document.getElementById('comments-list');
        
        if (comments.length === 0) {
            commentsList.innerHTML = '<div class="comments-loading">No comments yet. Be the first to comment!</div>';
            return;
        }
        
        commentsList.innerHTML = '';
        comments.forEach(comment => {
            const commentElement = this.createCommentElement(comment);
            commentsList.appendChild(commentElement);
        });
    }
    
    appendComments(comments) {
        const commentsList = document.getElementById('comments-list');
        
        comments.forEach(comment => {
            const commentElement = this.createCommentElement(comment);
            commentsList.appendChild(commentElement);
        });
    }
    
    prependComment(comment) {
        const commentsList = document.getElementById('comments-list');
        const commentElement = this.createCommentElement(comment);
        
        // Remove "no comments" message if present
        const noCommentsMsg = commentsList.querySelector('.comments-loading');
        if (noCommentsMsg) {
            noCommentsMsg.remove();
        }
        
        commentsList.insertBefore(commentElement, commentsList.firstChild);
    }
    
    createCommentElement(comment) {
        const commentDiv = document.createElement('div');
        commentDiv.className = 'comment-item';
        commentDiv.dataset.commentId = comment.id;
        
        const timeAgo = this.formatTimeAgo(new Date(comment.created_at));
        
        commentDiv.innerHTML = `
            <div class="comment-header">
                <span class="comment-author">${this.escapeHtml(comment.user_name)}</span>
                <span class="comment-date">${timeAgo}</span>
            </div>
            <div class="comment-content">${this.escapeHtml(comment.content)}</div>
            <div class="comment-actions">
                <button class="comment-action reply-action" data-comment-id="${comment.id}">
                    Reply${comment.reply_count > 0 ? ` (${comment.reply_count})` : ''}
                </button>
                ${this.userId === comment.user_id ? `
                    <button class="comment-action edit-action" data-comment-id="${comment.id}">Edit</button>
                    <button class="comment-action delete-action" data-comment-id="${comment.id}">Delete</button>
                ` : ''}
            </div>
            <div class="comment-replies" id="replies-${comment.id}" style="display: none;"></div>
        `;
        
        // Add event listeners
        const replyButton = commentDiv.querySelector('.reply-action');
        const editButton = commentDiv.querySelector('.edit-action');
        const deleteButton = commentDiv.querySelector('.delete-action');
        
        replyButton?.addEventListener('click', () => this.showReplyForm(comment.id));
        editButton?.addEventListener('click', () => this.editComment(comment.id));
        deleteButton?.addEventListener('click', () => this.deleteComment(comment.id));
        
        return commentDiv;
    }
    
    async showReplyForm(commentId) {
        const repliesContainer = document.getElementById(`replies-${commentId}`);
        
        // Toggle visibility
        if (repliesContainer.style.display === 'none') {
            // Load replies if not already loaded
            if (repliesContainer.children.length === 0) {
                await this.loadReplies(commentId);
            }
            repliesContainer.style.display = 'block';
        } else {
            repliesContainer.style.display = 'none';
        }
    }
    
    async loadReplies(commentId) {
        if (!this.currentVideoId) return;
        
        try {
            const response = await fetch(
                `/api/videos/${this.currentVideoId}/comments/${commentId}/replies?page=1&limit=10`
            );
            
            if (response.ok) {
                const data = await response.json();
                const repliesContainer = document.getElementById(`replies-${commentId}`);
                
                // Clear existing content
                repliesContainer.innerHTML = '';
                
                // Add replies
                data.replies.forEach(reply => {
                    const replyElement = this.createReplyElement(reply);
                    repliesContainer.appendChild(replyElement);
                });
                
                // Add reply form
                const replyForm = this.createReplyForm(commentId);
                repliesContainer.appendChild(replyForm);
                
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to load replies:', error);
        }
    }
    
    createReplyElement(reply) {
        const replyDiv = document.createElement('div');
        replyDiv.className = 'comment-reply';
        replyDiv.dataset.replyId = reply.id;
        
        const timeAgo = this.formatTimeAgo(new Date(reply.created_at));
        
        replyDiv.innerHTML = `
            <div class="comment-header">
                <span class="comment-author">${this.escapeHtml(reply.user_name)}</span>
                <span class="comment-date">${timeAgo}</span>
            </div>
            <div class="comment-content">${this.escapeHtml(reply.content)}</div>
            ${this.userId === reply.user_id ? `
                <div class="comment-actions">
                    <button class="comment-action edit-action" data-reply-id="${reply.id}">Edit</button>
                    <button class="comment-action delete-action" data-reply-id="${reply.id}">Delete</button>
                </div>
            ` : ''}
        `;
        
        return replyDiv;
    }
    
    createReplyForm(parentCommentId) {
        const formDiv = document.createElement('div');
        formDiv.className = 'reply-form';
        formDiv.innerHTML = `
            <textarea class="reply-input" placeholder="Write a reply..." maxlength="2000" rows="2"></textarea>
            <div class="reply-actions">
                <button class="reply-button secondary cancel-reply">Cancel</button>
                <button class="reply-button primary submit-reply" disabled>Reply</button>
            </div>
        `;
        
        const textarea = formDiv.querySelector('.reply-input');
        const submitButton = formDiv.querySelector('.submit-reply');
        const cancelButton = formDiv.querySelector('.cancel-reply');
        
        // Enable/disable submit based on content
        textarea.addEventListener('input', () => {
            submitButton.disabled = !textarea.value.trim();
        });
        
        // Submit reply
        submitButton.addEventListener('click', async () => {
            const content = textarea.value.trim();
            if (!content) return;
            
            try {
                const response = await fetch(`/api/videos/${this.currentVideoId}/comments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        content: content,
                        parent_comment_id: parentCommentId
                    })
                });
                
                if (response.ok) {
                    const reply = await response.json();
                    
                    // Add reply to UI
                    const replyElement = this.createReplyElement(reply);
                    formDiv.parentNode.insertBefore(replyElement, formDiv);
                    
                    // Clear form
                    textarea.value = '';
                    submitButton.disabled = true;
                    
                    // Update reply count
                    this.updateReplyCount(parentCommentId, 1);
                    
                } else if (response.status === 401) {
                    this.showLoginPrompt();
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            } catch (error) {
                console.error('Failed to submit reply:', error);
                this.showError('Failed to submit reply. Please try again.');
            }
        });
        
        // Cancel reply
        cancelButton.addEventListener('click', () => {
            textarea.value = '';
            submitButton.disabled = true;
        });
        
        return formDiv;
    }
    
    updateCommentsTitle(count) {
        const title = document.getElementById('comments-title');
        if (title) {
            title.textContent = `Comments (${count})`;
        }
    }
    
    incrementCommentsCount() {
        const title = document.getElementById('comments-title');
        if (title) {
            const match = title.textContent.match(/Comments \((\d+)\)/);
            if (match) {
                const newCount = parseInt(match[1]) + 1;
                title.textContent = `Comments (${newCount})`;
            } else {
                title.textContent = 'Comments (1)';
            }
        }
    }
    
    updateLoadMoreButton(pagination) {
        const loadMoreButton = document.getElementById('load-more-comments');
        
        if (pagination.page < pagination.pages) {
            loadMoreButton.style.display = 'block';
            loadMoreButton.textContent = `Load more comments (${pagination.total - (pagination.page * pagination.limit)} remaining)`;
        } else {
            loadMoreButton.style.display = 'none';
        }
    }
    
    async loadMoreComments() {
        const nextPage = (this.currentCommentsPage || 1) + 1;
        await this.loadComments(nextPage, this.currentCommentsSort || 'newest');
    }
    
    showCommentsError(message) {
        const commentsList = document.getElementById('comments-list');
        commentsList.innerHTML = `<div class="comments-loading" style="color: var(--error-color);">${message}</div>`;
    }
    
    formatTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Cleanup
    destroy() {
        // End viewing session before cleanup
        this.endViewingSession();
        
        if (this.hls) {
            this.hls.destroy();
        }
        
        if (this.progressUpdateInterval) {
            clearInterval(this.progressUpdateInterval);
        }
        
        if (this.statsUpdateInterval) {
            clearInterval(this.statsUpdateInterval);
        }
    }
}

// Initialize global player instance
window.adaptiveVideoPlayer = new AdaptiveVideoPlayer();
