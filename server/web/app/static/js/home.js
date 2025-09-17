// Home page JavaScript

class HomeManager {
    constructor() {
        this.sections = {};
        this.init();
    }

    init() {
        this.loadDiscoverySections();
    }

    async loadDiscoverySections() {
        try {
            this.showLoading();
            
            const response = await fetch('/api/discover/sections', {
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                this.sections = await response.json();
                this.renderDiscoverySections();
            } else {
                console.error('Failed to load discovery sections');
                this.showError('Failed to load content');
            }
        } catch (error) {
            console.error('Error loading discovery sections:', error);
            this.showError('Error loading content');
        }
    }

    renderDiscoverySections() {
        const container = document.getElementById('discovery-sections');
        
        if (Object.keys(this.sections).length === 0) {
            container.innerHTML = `
                <div class="empty-section">
                    <h3>No Content Available</h3>
                    <p>Start by uploading some videos or exploring existing content.</p>
                </div>
            `;
            return;
        }

        let sectionsHtml = '';

        // Define section configurations
        const sectionConfigs = {
            'trending': {
                title: 'Trending Now',
                description: 'Popular videos this week',
                link: '/browse?sort=most_viewed',
                className: 'section-trending'
            },
            'popular': {
                title: 'Most Popular',
                description: 'Most liked videos this month',
                link: '/browse?sort=most_liked',
                className: 'section-popular'
            },
            'latest': {
                title: 'Latest Uploads',
                description: 'Recently uploaded videos',
                link: '/browse?sort=newest',
                className: 'section-latest'
            },
            'recommended': {
                title: 'Recommended for You',
                description: 'Personalized recommendations',
                link: '/browse',
                className: 'section-recommended'
            }
        };

        // Render main sections
        for (const [sectionKey, config] of Object.entries(sectionConfigs)) {
            if (this.sections[sectionKey] && this.sections[sectionKey].length > 0) {
                sectionsHtml += this.renderSection(
                    sectionKey,
                    config.title,
                    this.sections[sectionKey],
                    config.link,
                    config.className
                );
            }
        }

        // Render category sections
        for (const [sectionKey, videos] of Object.entries(this.sections)) {
            if (sectionKey.startsWith('category_') && videos.length > 0) {
                const categoryName = sectionKey.replace('category_', '');
                sectionsHtml += this.renderSection(
                    sectionKey,
                    `${this.capitalizeFirst(categoryName)} Videos`,
                    videos,
                    `/browse?category=${categoryName}`,
                    'section-category'
                );
            }
        }

        container.innerHTML = sectionsHtml;
    }

    renderSection(sectionKey, title, videos, link, className = '') {
        if (!videos || videos.length === 0) return '';

        return `
            <div class="discovery-section ${className}" data-section="${sectionKey}">
                <div class="section-header">
                    <h2 class="section-title">${this.escapeHtml(title)}</h2>
                    <a href="${link}" class="section-link">View All</a>
                </div>
                <div class="video-carousel">
                    ${videos.map(video => this.renderVideoCard(video)).join('')}
                </div>
            </div>
        `;
    }

    renderVideoCard(video) {
        return `
            <div class="video-card" onclick="homeManager.playVideo('${video.id}')">
                <div class="video-thumbnail">
                    ${video.thumbnail_s3_key ? 
                        `<img src="${this.getThumbnailUrl(video.thumbnail_s3_key)}" alt="${this.escapeHtml(video.title)}" />` :
                        '<div style="display: flex; align-items: center; justify-content: center; height: 100%; background: #f0f0f0; color: #666; font-size: 2rem;">🎥</div>'
                    }
                    <div class="video-duration">${this.formatDuration(video.duration_seconds)}</div>
                </div>
                <div class="video-info">
                    <h3 class="video-title">${this.escapeHtml(video.title)}</h3>
                    <div class="video-creator">${this.escapeHtml(video.creator_name)}</div>
                    <div class="video-meta">
                        <div class="video-stats">
                            <span>${video.view_count || 0} views</span>
                            <span>${this.formatDate(video.created_at)}</span>
                        </div>
                        ${video.category ? `<span class="video-category">${video.category}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    showLoading() {
        const container = document.getElementById('discovery-sections');
        container.innerHTML = `
            <div class="loading">
                <div class="loading-spinner"></div>
                <p>Loading content...</p>
            </div>
        `;
    }

    showError(message) {
        const container = document.getElementById('discovery-sections');
        container.innerHTML = `
            <div class="empty-section">
                <h3>Error Loading Content</h3>
                <p>${this.escapeHtml(message)}</p>
                <button onclick="homeManager.loadDiscoverySections()" class="btn btn-primary" style="margin-top: 1rem;">
                    Try Again
                </button>
            </div>
        `;
    }

    playVideo(videoId) {
        window.location.href = `/video/${videoId}`;
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

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffTime = Math.abs(now - date);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays === 1) {
            return 'Yesterday';
        } else if (diffDays < 7) {
            return `${diffDays} days ago`;
        } else if (diffDays < 30) {
            const weeks = Math.floor(diffDays / 7);
            return `${weeks} week${weeks > 1 ? 's' : ''} ago`;
        } else if (diffDays < 365) {
            const months = Math.floor(diffDays / 30);
            return `${months} month${months > 1 ? 's' : ''} ago`;
        } else {
            const years = Math.floor(diffDays / 365);
            return `${years} year${years > 1 ? 's' : ''} ago`;
        }
    }

    getThumbnailUrl(s3Key) {
        // This would typically use your CDN or S3 URL
        return `/api/media/thumbnail/${s3Key}`;
    }

    getAuthHeaders() {
        const token = localStorage.getItem('auth_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the home manager when the page loads
let homeManager;
document.addEventListener('DOMContentLoaded', () => {
    homeManager = new HomeManager();
});