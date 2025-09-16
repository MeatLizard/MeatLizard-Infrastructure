// AI Chat System JavaScript
class ChatInterface {
    constructor() {
        this.sessionId = null;
        this.isConnected = false;
        this.isLoading = false;
        
        this.initializeElements();
        this.setupEventListeners();
        this.initializeSession();
    }
    
    initializeElements() {
        this.messagesContainer = document.getElementById('messages');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.statusDot = document.getElementById('status-dot');
        this.statusText = document.getElementById('status-text');
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.sessionStart = document.getElementById('session-start');
    }
    
    setupEventListeners() {
        // Send message on button click
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Send message on Enter key
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Enable/disable send button based on input
        this.messageInput.addEventListener('input', () => {
            const hasText = this.messageInput.value.trim().length > 0;
            this.sendButton.disabled = !hasText || this.isLoading;
        });
        
        // Sidebar navigation
        document.querySelectorAll('.sidebar .icon').forEach(icon => {
            icon.addEventListener('click', (e) => this.handleSidebarClick(e));
        });
    }
    
    async initializeSession() {
        try {
            this.updateStatus('connecting', 'Connecting...');
            
            // Create a new session
            const response = await fetch('/sessions/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_label: `WebUser_${Date.now()}`
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.sessionId = data.session_id;
            
            this.updateStatus('connected', 'Connected');
            this.sendButton.disabled = false;
            this.messageInput.disabled = false;
            this.messageInput.focus();
            
            // Update session start timestamp
            this.sessionStart.textContent = `Session started - ${new Date().toLocaleString()}`;
            
        } catch (error) {
            console.error('Failed to initialize session:', error);
            this.updateStatus('error', 'Connection failed');
            this.addSystemMessage('Failed to connect to the server. Please refresh the page to try again.');
        }
    }
    
    updateStatus(status, text) {
        this.statusDot.className = `status-dot ${status}`;
        this.statusText.textContent = text;
        this.isConnected = status === 'connected';
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isLoading || !this.isConnected) return;
        
        // Add user message to chat
        this.addMessage(message, 'user');
        this.messageInput.value = '';
        this.sendButton.disabled = true;
        
        // Show loading state
        this.setLoading(true);
        
        try {
            // Send message to API
            const response = await fetch('/chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    message: message
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Add AI response to chat
            if (data.response) {
                this.addMessage(data.response, 'bot');
            } else {
                this.addMessage('I apologize, but I couldn\'t generate a response. Please try again.', 'error');
            }
            
        } catch (error) {
            console.error('Failed to send message:', error);
            this.addMessage('Sorry, there was an error sending your message. Please try again.', 'error');
        } finally {
            this.setLoading(false);
            this.messageInput.focus();
        }
    }
    
    addMessage(content, type) {
        const bubble = document.createElement('div');
        bubble.className = `bubble ${type}`;
        bubble.textContent = content;
        
        // Add timestamp for user messages
        if (type === 'user') {
            const timestamp = document.createElement('div');
            timestamp.className = 'reply-note';
            timestamp.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            this.messagesContainer.appendChild(bubble);
            this.messagesContainer.appendChild(timestamp);
        } else {
            this.messagesContainer.appendChild(bubble);
        }
        
        this.scrollToBottom();
    }
    
    addSystemMessage(content) {
        const bubble = document.createElement('div');
        bubble.className = 'bubble system';
        bubble.textContent = content;
        this.messagesContainer.appendChild(bubble);
        this.scrollToBottom();
    }
    
    setLoading(loading) {
        this.isLoading = loading;
        this.loadingOverlay.classList.toggle('show', loading);
        this.messageInput.disabled = loading;
        this.sendButton.disabled = loading || this.messageInput.value.trim().length === 0;
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    handleSidebarClick(event) {
        const clickedIcon = event.currentTarget;
        const title = clickedIcon.getAttribute('title');
        
        // Remove active class from all icons
        document.querySelectorAll('.sidebar .icon').forEach(icon => {
            icon.classList.remove('active');
        });
        
        // Add active class to clicked icon
        clickedIcon.classList.add('active');
        
        // Handle different sidebar actions
        switch (title) {
            case 'Settings':
                this.addSystemMessage('Settings panel coming soon...');
                break;
            case 'History':
                this.addSystemMessage('Chat history feature coming soon...');
                break;
            case 'AI Chat':
                // Already in chat view
                break;
        }
    }
    
    // Utility method to format timestamps
    formatTimestamp(date) {
        const now = new Date();
        const messageDate = new Date(date);
        
        if (now.toDateString() === messageDate.toDateString()) {
            return messageDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        } else {
            return messageDate.toLocaleDateString() + ' ' + 
                   messageDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        }
    }
}

// Initialize chat interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ChatInterface();
});

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        // Page became visible, could refresh connection status
        console.log('Page became visible');
    }
});

// Handle online/offline status
window.addEventListener('online', () => {
    console.log('Connection restored');
});

window.addEventListener('offline', () => {
    console.log('Connection lost');
});