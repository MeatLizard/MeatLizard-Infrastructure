// Channels management JavaScript

class ChannelManager {
    constructor() {
        this.channels = [];
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadChannels();
    }

    setupEventListeners() {
        // Create channel button
        document.getElementById('create-channel-btn').addEventListener('click', () => {
            this.openCreateChannelModal();
        });

        // Create channel form
        document.getElementById('create-channel-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createChannel();
        });

        // Modal close buttons
        document.querySelectorAll('.close').forEach(closeBtn => {
            closeBtn.addEventListener('click', (e) => {
                e.target.closest('.modal').style.display = 'none';
            });
        });

        // Close modal when clicking outside
        window.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                e.target.style.display = 'none';
            }
        });

        // Auto-generate slug from name
        document.getElementById('channel-name').addEventListener('input', (e) => {
            const slugInput = document.getElementById('channel-slug');
            if (!slugInput.value) {
                slugInput.value = this.generateSlug(e.target.value);
            }
        });
    }

    async loadChannels() {
        try {
            const response = await fetch('/api/channels/', {
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });

            if (response.ok) {
                this.channels = await response.json();
                this.renderChannels();
            } else {
                console.error('Failed to load channels');
                this.showError('Failed to load channels');
            }
        } catch (error) {
            console.error('Error loading channels:', error);
            this.showError('Error loading channels');
        }
    }

    renderChannels() {
        const grid = document.getElementById('channels-grid');
        
        if (this.channels.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <h3>No Channels Yet</h3>
                    <p>Create your first channel to start organizing your videos.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.channels.map(channel => `
            <div class="channel-card" onclick="channelManager.openChannelDetails('${channel.id}')">
                <div class="channel-banner" style="background: ${this.getChannelColor(channel.category)}">
                    <div class="channel-avatar">
                        ${channel.name.charAt(0).toUpperCase()}
                    </div>
                </div>
                <div class="channel-info">
                    <h3 class="channel-name">${this.escapeHtml(channel.name)}</h3>
                    <p class="channel-description">${this.escapeHtml(channel.description || 'No description')}</p>
                    <div class="channel-meta">
                        <div class="channel-stats">
                            <span>0 videos</span>
                            <span>0 playlists</span>
                        </div>
                        <div class="channel-badges">
                            ${channel.category ? `<span class="channel-category">${channel.category}</span>` : ''}
                            <span class="channel-visibility visibility-${channel.visibility}">${channel.visibility}</span>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    openCreateChannelModal() {
        document.getElementById('create-channel-modal').style.display = 'block';
        document.getElementById('create-channel-form').reset();
    }

    closeCreateChannelModal() {
        document.getElementById('create-channel-modal').style.display = 'none';
    }

    async createChannel() {
        const form = document.getElementById('create-channel-form');
        const formData = new FormData(form);
        
        const channelData = {
            name: formData.get('name'),
            description: formData.get('description') || null,
            slug: formData.get('slug') || null,
            category: formData.get('category') || null,
            visibility: formData.get('visibility')
        };

        try {
            const response = await fetch('/api/channels/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getAuthToken()}`
                },
                body: JSON.stringify(channelData)
            });

            if (response.ok) {
                const newChannel = await response.json();
                this.channels.unshift(newChannel);
                this.renderChannels();
                this.closeCreateChannelModal();
                this.showSuccess('Channel created successfully!');
            } else {
                const error = await response.json();
                this.showError(error.detail || 'Failed to create channel');
            }
        } catch (error) {
            console.error('Error creating channel:', error);
            this.showError('Error creating channel');
        }
    }

    async openChannelDetails(channelId) {
        try {
            const response = await fetch(`/api/channels/${channelId}`, {
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });

            if (response.ok) {
                const channel = await response.json();
                this.renderChannelDetails(channel);
                document.getElementById('channel-details-modal').style.display = 'block';
            } else {
                this.showError('Failed to load channel details');
            }
        } catch (error) {
            console.error('Error loading channel details:', error);
            this.showError('Error loading channel details');
        }
    }

    renderChannelDetails(channel) {
        const content = document.getElementById('channel-details-content');
        document.getElementById('channel-details-title').textContent = channel.name;
        
        content.innerHTML = `
            <div style="padding: 1.5rem;">
                <div class="channel-detail-section">
                    <h4>Channel Information</h4>
                    <p><strong>Name:</strong> ${this.escapeHtml(channel.name)}</p>
                    <p><strong>Slug:</strong> ${this.escapeHtml(channel.slug)}</p>
                    <p><strong>Description:</strong> ${this.escapeHtml(channel.description || 'No description')}</p>
                    <p><strong>Category:</strong> ${this.escapeHtml(channel.category || 'None')}</p>
                    <p><strong>Visibility:</strong> <span class="channel-visibility visibility-${channel.visibility}">${channel.visibility}</span></p>
                    <p><strong>Created:</strong> ${new Date(channel.created_at).toLocaleDateString()}</p>
                </div>
                
                <div class="channel-actions" style="margin-top: 2rem; display: flex; gap: 1rem;">
                    <button class="btn btn-primary" onclick="channelManager.editChannel('${channel.id}')">Edit Channel</button>
                    <button class="btn btn-secondary" onclick="channelManager.viewChannelVideos('${channel.id}')">View Videos</button>
                    <button class="btn btn-secondary" onclick="channelManager.viewChannelPlaylists('${channel.id}')">View Playlists</button>
                </div>
            </div>
        `;
    }

    generateSlug(name) {
        return name
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .trim('-');
    }

    getChannelColor(category) {
        const colors = {
            gaming: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            education: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            entertainment: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
            music: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
            technology: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
            sports: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
            news: 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
            other: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
        };
        return colors[category] || colors.other;
    }

    getAuthToken() {
        // This would typically come from your authentication system
        return localStorage.getItem('auth_token') || '';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showSuccess(message) {
        // Implement your success notification system
        alert(message);
    }

    showError(message) {
        // Implement your error notification system
        alert(message);
    }

    editChannel(channelId) {
        // Implement channel editing functionality
        console.log('Edit channel:', channelId);
    }

    viewChannelVideos(channelId) {
        // Navigate to channel videos page
        window.location.href = `/channels/${channelId}/videos`;
    }

    viewChannelPlaylists(channelId) {
        // Navigate to channel playlists page
        window.location.href = `/channels/${channelId}/playlists`;
    }
}

// Initialize the channel manager when the page loads
let channelManager;
document.addEventListener('DOMContentLoaded', () => {
    channelManager = new ChannelManager();
});

// Global functions for modal management
function closeCreateChannelModal() {
    channelManager.closeCreateChannelModal();
}