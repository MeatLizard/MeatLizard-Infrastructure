// Browse page JavaScript

class BrowseManager {
    constructor() {
        this.currentTab = 'videos';
        this.currentPage = 1;
        this.currentFilters = {
            search: '',
            category: '',
            sort: 'newest',
            duration: ''
        };
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadCategories();
        this.loadTrendingVideos();
        this.loadContent();
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // Search
        document.getElementById('search-btn').addEventListener('click', () => {
            this.performSearch();
        });

        document.getElementById('search-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.performSearch();
            }
        });

        // Filters
        document.getElementById('category-filter').addEventListener('change', (e) => {
            this.currentFilters.category = e.target.value;
            this.loadContent();
        });

        document.getElementById('sort-filter').addEventListener('change', (e) => {
            this.currentFilters.sort = e.target.value;
            this.loadContent();
        });

        document.getElementById('duration-filter').addEventListener('change', (e) => {
            this.currentFilters.duration = e.target.value;
            this.loadContent();
        });

        // Clear filters
        document.getElementById('clear-filters-btn').addEventListener('click', () => {
            this.clearFilters();
        });
    }

    switchTab(tab) {
        // Update active tab button
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

        // Update active tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tab}-tab`).classList.add('active');

        this.currentTab = tab;
        this.currentPage = 1;
        this.loadContent();
    }

    performSearch() {
        const searchInput = document.getElementById('search-input');
        this.currentFilters.search = searchInput.value.trim();
        this.currentPage = 1;
        
        if (this.currentFilters.search) {
            this.loadSearchResults();
        } else {
            this.loadContent();
        }
    }

    clearFilters() {
        this.currentFilters = {
            search: '',
            category: '',
            sort: 'newest',
            duration: ''
        };
        
        document.getElementById('search-input').value = '';
        document.getElementById('category-filter').value = '';
        document.getElementById('sort-filter').value = 'newest';
        document.getElementById('duration-filter').value = '';
        
        this.currentPage = 1;
        this.loadContent();
    }

    async loadContent() {
        if (this.currentTab === 'videos') {
            await this.loadVideos();
        } else if (this.currentTab === 'channels') {
            await this.loadChannels();
        } else if (this.currentTab === 'playlists') {
            await this.loadPlaylists();
        }
    }

    async loadVideos() {
        try {
            this.showLoading('video-grid');
            
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: 20,
                sort: this.currentFilters.sort
            });

            if (this.currentFilters.category) {
                params.append('category', this.currentFilters.category);
            }

            if (this.currentFilters.search) {
                params.append('q', this.currentFilters.search);
            }

            if (this.currentFilters.duration) {
                const [min, max] = this.currentFilters.duration.split('-');
                if (min) params.append('min_duration', min);
                if (max) params.append('max_duration', max);
            }

            const response = await fetch(`/api/discover/videos?${params}`, {
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                this.renderVideos(data.videos);
                this.renderPagination(data);
                this.updateResultsCount(data.total, 'videos');
            } else {
                this.showError('Failed to load videos');
            }
        } catch (error) {
            console.error('Error loading videos:', error);
            this.showError('Error loading videos');
        }
    }

    async loadSearchResults() {
        try {
            this.showLoading(`${this.currentTab}-grid`);
            
            const params = new URLSearchParams({
                q: this.currentFilters.search,
                page: this.currentPage,
                per_page: 20
            });

            const response = await fetch(`/api/discover/search?${params}`, {
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                
                if (this.currentTab === 'videos' && data.videos) {
                    this.renderVideos(data.videos.items);
                    this.updateResultsCount(data.videos.total, 'videos');
                } else if (this.currentTab === 'channels' && data.channels) {
                    this.renderChannels(data.channels.items);
                    this.updateResultsCount(data.channels.total, 'channels');
                } else if (this.currentTab === 'playlists' && data.playlists) {
                    this.renderPlaylists(data.playlists.items);
                    this.updateResultsCount(data.playlists.total, 'playlists');
                }
            } else {
                this.showError('Failed to search content');
            }
        } catch (error) {
            console.error('Error searching content:', error);
            this.showError('Error searching content');
        }
    }

    renderVideos(videos) {
        const grid = document.getElementById('video-grid');
        
        if (videos.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h3>No Videos Found</h3>
                    <p>Try adjusting your search or filters.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = videos.map(video => `
            <div class="video-card" onclick="browseManager.playVideo('${video.id}')">
                <div class="video-thumbnail">
                    ${video.thumbnail_s3_key ? 
                        `<img src="${this.getThumbnailUrl(video.thumbnail_s3_key)}" alt="${this.escapeHtml(video.title)}" />` :
                        '<div style="display: flex; align-items: center; justify-content: center; height: 100%; background: #f0f0f0; color: #666;">No Thumbnail</div>'
                    }
                    <div class="video-duration">${this.formatDuration(video.duration_seconds)}</div>
                </div>
                <div class="video-info">
                    <h3 class="video-title">${this.escapeHtml(video.title)}</h3>
                    <div class="video-creator">${this.escapeHtml(video.creator_name)}</div>
                    <div class="video-meta">
                        <div class="video-stats">
                            <span>${video.view_count || 0} views</span>
                            <span>${video.like_count || 0} likes</span>
                        </div>
                        ${video.category ? `<span class="video-category">${video.category}</span>` : ''}
                    </div>
                </div>
            </div>
        `).join('');
    }

    renderChannels(channels) {
        const grid = document.getElementById('channel-grid');
        
        if (channels.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h3>No Channels Found</h3>
                    <p>Try adjusting your search or filters.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = channels.map(channel => `
            <div class="channel-card" onclick="browseManager.viewChannel('${channel.id}')">
                <div class="channel-banner">
                    <div class="channel-avatar">
                        ${channel.name.charAt(0).toUpperCase()}
                    </div>
                </div>
                <div class="channel-info">
                    <h3 class="channel-name">${this.escapeHtml(channel.name)}</h3>
                    <p class="channel-description">${this.escapeHtml(channel.description || 'No description')}</p>
                    <div class="channel-meta">
                        <div class="channel-stats">
                            <span>${channel.video_count || 0} videos</span>
                        </div>
                        ${channel.category ? `<span class="channel-category">${channel.category}</span>` : ''}
                    </div>
                </div>
            </div>
        `).join('');
    }

    renderPlaylists(playlists) {
        const grid = document.getElementById('playlist-grid');
        
        if (playlists.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h3>No Playlists Found</h3>
                    <p>Try adjusting your search or filters.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = playlists.map(playlist => `
            <div class="playlist-card" onclick="browseManager.viewPlaylist('${playlist.id}')">
                <div class="playlist-thumbnail">
                    📋
                </div>
                <div class="playlist-info">
                    <h3 class="playlist-name">${this.escapeHtml(playlist.name)}</h3>
                    <div class="playlist-creator">${this.escapeHtml(playlist.creator_name)}</div>
                    <div class="playlist-meta">
                        <span>${playlist.video_count || 0} videos</span>
                        ${playlist.channel_name ? `<span>in ${this.escapeHtml(playlist.channel_name)}</span>` : ''}
                    </div>
                </div>
            </div>
        `).join('');
    }

    renderPagination(data) {
        const pagination = document.getElementById('pagination');
        
        if (data.total <= data.per_page) {
            pagination.innerHTML = '';
            return;
        }

        const totalPages = Math.ceil(data.total / data.per_page);
        let paginationHtml = '';

        // Previous button
        paginationHtml += `
            <button ${!data.has_prev ? 'disabled' : ''} onclick="browseManager.goToPage(${data.page - 1})">
                Previous
            </button>
        `;

        // Page numbers
        const startPage = Math.max(1, data.page - 2);
        const endPage = Math.min(totalPages, data.page + 2);

        if (startPage > 1) {
            paginationHtml += `<button onclick="browseManager.goToPage(1)">1</button>`;
            if (startPage > 2) {
                paginationHtml += `<span>...</span>`;
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            paginationHtml += `
                <button class="${i === data.page ? 'active' : ''}" onclick="browseManager.goToPage(${i})">
                    ${i}
                </button>
            `;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHtml += `<span>...</span>`;
            }
            paginationHtml += `<button onclick="browseManager.goToPage(${totalPages})">${totalPages}</button>`;
        }

        // Next button
        paginationHtml += `
            <button ${!data.has_next ? 'disabled' : ''} onclick="browseManager.goToPage(${data.page + 1})">
                Next
            </button>
        `;

        pagination.innerHTML = paginationHtml;
    }

    goToPage(page) {
        this.currentPage = page;
        this.loadContent();
    }

    async loadCategories() {
        try {
            const response = await fetch('/api/discover/categories');
            if (response.ok) {
                const categories = await response.json();
                this.renderCategoryFilter(categories);
                this.renderPopularCategories(categories);
            }
        } catch (error) {
            console.error('Error loading categories:', error);
        }
    }

    renderCategoryFilter(categories) {
        const select = document.getElementById('category-filter');
        const currentValue = select.value;
        
        select.innerHTML = '<option value="">All Categories</option>' +
            categories.map(cat => 
                `<option value="${cat.name}">${cat.name} (${cat.video_count})</option>`
            ).join('');
        
        select.value = currentValue;
    }

    renderPopularCategories(categories) {
        const container = document.getElementById('popular-categories');
        
        container.innerHTML = categories.slice(0, 8).map(category => `
            <div class="category-item" onclick="browseManager.filterByCategory('${category.name}')">
                <span class="category-name">${category.name}</span>
                <span class="category-count">${category.video_count}</span>
            </div>
        `).join('');
    }

    async loadTrendingVideos() {
        try {
            const response = await fetch('/api/discover/trending?limit=10', {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                const videos = await response.json();
                this.renderTrendingVideos(videos);
            }
        } catch (error) {
            console.error('Error loading trending videos:', error);
        }
    }

    renderTrendingVideos(videos) {
        const container = document.getElementById('trending-videos');
        
        container.innerHTML = videos.map(video => `
            <div class="trending-video" onclick="browseManager.playVideo('${video.id}')">
                <div class="trending-thumbnail">
                    ${video.thumbnail_s3_key ? 
                        `<img src="${this.getThumbnailUrl(video.thumbnail_s3_key)}" alt="${this.escapeHtml(video.title)}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 4px;" />` :
                        '<div style="width: 100%; height: 100%; background: #f0f0f0; border-radius: 4px;"></div>'
                    }
                </div>
                <div class="trending-info">
                    <div class="trending-title">${this.escapeHtml(video.title)}</div>
                    <div class="trending-creator">${this.escapeHtml(video.creator_name)}</div>
                </div>
            </div>
        `).join('');
    }

    filterByCategory(category) {
        document.getElementById('category-filter').value = category;
        this.currentFilters.category = category;
        this.currentPage = 1;
        this.switchTab('videos');
    }

    updateResultsCount(total, type) {
        const countElement = document.getElementById('results-count');
        const titleElement = document.getElementById('results-title');
        
        countElement.textContent = `${total} ${type} found`;
        
        if (this.currentFilters.search) {
            titleElement.textContent = `Search Results for "${this.currentFilters.search}"`;
        } else if (this.currentFilters.category) {
            titleElement.textContent = `${this.currentFilters.category} ${type}`;
        } else {
            titleElement.textContent = `All ${type}`;
        }
    }

    showLoading(containerId) {
        const container = document.getElementById(containerId);
        container.innerHTML = `
            <div class="loading">
                <p>Loading...</p>
            </div>
        `;
    }

    showError(message) {
        console.error(message);
        // Implement your error notification system
    }

    playVideo(videoId) {
        window.location.href = `/video/${videoId}`;
    }

    viewChannel(channelId) {
        window.location.href = `/channels/${channelId}`;
    }

    viewPlaylist(playlistId) {
        window.location.href = `/playlists/${playlistId}`;
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

    getThumbnailUrl(s3Key) {
        // This would typically use your CDN or S3 URL
        return `/api/media/thumbnail/${s3Key}`;
    }

    getAuthHeaders() {
        const token = localStorage.getItem('auth_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize the browse manager when the page loads
let browseManager;
document.addEventListener('DOMContentLoaded', () => {
    browseManager = new BrowseManager();
});