/**
 * Messaging Application - JavaScript
 * Handles real-time messaging, UI interactions, and Socket.IO communication
 */

class MessagingApp {
  constructor() {
    this.socket = null;
    this.currentConversationId = null;
    this.isTyping = false;
    this.typingTimeout = null;
    this.messageBuffer = [];
    this.unreadCount = 0;
    this.init();
  }

  init() {
    this.connectSocket();
    this.attachEventListeners();
    this.loadInitialData();
    // Scroll to bottom after page loads
    setTimeout(() => this.scrollToBottom(), 100);
  }

  // ==================== SOCKET.IO SETUP ====================

  connectSocket() {
    // Socket.IO already initialized in templates
    if (typeof io === 'undefined') return;

    this.socket = io();

    this.socket.on('connect', () => {
      console.log('Connected to messaging server');
      // Join conversation after socket is connected
      const convId = document.querySelector('[data-conversation-id]')?.dataset
        .conversationId;
      if (convId) {
        this.currentConversationId = parseInt(convId);
        this.socket.emit('join_conversation', { conversation_id: convId });
      }
    });

    this.socket.on('new_message', (data) => {
      console.log('📨 New message received:', data);
      this.handleNewMessage(data);
    });

    this.socket.on('message_read', (data) => {
      this.handleMessageRead(data);
    });

    this.socket.on('user_typing', (data) => {
      this.showTypingIndicator(data);
    });

    this.socket.on('user_stopped_typing', (data) => {
      this.hideTypingIndicator(data);
    });

    this.socket.on('disconnect', () => {
      console.log('Disconnected from messaging server');
    });
  }

  // ==================== MESSAGE HANDLING ====================

  handleNewMessage(messageData) {
    // Get current user ID from DOM
    const currentUserId = parseInt(document.querySelector('[data-current-user-id]')?.dataset.currentUserId);
    const isOwnMessage = messageData.sender_id === currentUserId;
    
    // Only add to DOM if it's from another user
    if (!isOwnMessage) {
      this.addMessageToDOM(messageData, false);
      this.updateConversationPreview(messageData);
      this.incrementUnreadCount();

      // Auto-mark as read if viewing conversation
      if (this.currentConversationId === messageData.conversation_id) {
        this.markMessageAsRead(messageData.id);
      }
    }
  }

  handleMessageRead(data) {
    const messageEl = document.querySelector(
      `[data-message-id="${data.message_id}"]`
    );
    if (messageEl) {
      messageEl.classList.add('read');
      const statusIcon = messageEl.querySelector('.status-icon');
      if (statusIcon) {
        statusIcon.classList.remove('status-delivered');
        statusIcon.classList.add('status-read');
        statusIcon.innerHTML =
          '<i class="fas fa-check-double text-blue-500"></i>';
      }
    }
  }

  addMessageToDOM(messageData, isOwn = false) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    const messageEl = document.createElement('div');
    messageEl.className = `message-bubble ${isOwn ? 'own' : 'other'} animate-slide-in-up`;
    messageEl.setAttribute('data-message-id', messageData.id);

    const statusHTML = isOwn
      ? `<div class="message-status">
           <span class="status-icon status-delivered">
             <i class="fas fa-check text-gray-400"></i>
           </span>
         </div>`
      : '';

    messageEl.innerHTML = `
      <div class="message-content">
        <div class="message-text">${this.escapeHtml(messageData.content)}</div>
        <div class="message-time">${messageData.created_at_formatted}</div>
        ${statusHTML}
      </div>
    `;

    // Add action menu
    if (isOwn) {
      const menuBtn = document.createElement('button');
      menuBtn.className =
        'ml-2 text-gray-400 hover:text-gray-600 transition focus-ring';
      menuBtn.innerHTML = '<i class="fas fa-ellipsis-v"></i>';
      menuBtn.addEventListener('click', () =>
        this.showMessageMenu(messageData.id)
      );
      messageEl.appendChild(menuBtn);
    }

    chatMessages.appendChild(messageEl);
    this.scrollToBottom();
  }

  // ==================== MESSAGE ACTIONS ====================

  sendMessage() {
    const textarea = document.querySelector('.message-textarea');
    const content = textarea.value.trim();

    if (!content || !this.currentConversationId) return;

    const sendBtn = document.querySelector('.send-button');
    sendBtn.disabled = true;

    fetch(`/messages/send-message/${this.currentConversationId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCSRFToken(),
      },
      body: JSON.stringify({ content: content }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.addMessageToDOM(data.message, true);
          textarea.value = '';
          textarea.style.height = 'auto';
          this.stopTyping();
        } else {
          this.showNotification(data.error || 'Failed to send message', 'error');
        }
      })
      .catch((err) => {
        console.error('Error sending message:', err);
        this.showNotification('Error sending message', 'error');
      })
      .finally(() => {
        sendBtn.disabled = false;
      });
  }

  markMessageAsRead(messageId) {
    fetch(`/messages/mark-read/${messageId}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
      },
    }).catch((err) => console.error('Error marking message as read:', err));
  }

  deleteMessage(messageId) {
    if (!confirm('Are you sure you want to delete this message?')) return;

    fetch(`/messages/delete-message/${messageId}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
      },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
          if (msgEl) {
            msgEl.remove();
          }
          this.showNotification('Message deleted', 'success');
        }
      })
      .catch((err) => console.error('Error deleting message:', err));
  }

  // ==================== CONVERSATION ACTIONS ====================

  blockUser(conversationId) {
    if (!confirm('Block this user? You won\'t receive messages from them.')) {
      return;
    }

    fetch(`/messages/block-user/${conversationId}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
      },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.showNotification('User blocked', 'success');
          setTimeout(() => window.location.reload(), 1000);
        }
      })
      .catch((err) => console.error('Error blocking user:', err));
  }

  unblockUser(conversationId) {
    fetch(`/messages/unblock-user/${conversationId}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
      },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.showNotification('User unblocked', 'success');
          setTimeout(() => window.location.reload(), 1000);
        }
      })
      .catch((err) => console.error('Error unblocking user:', err));
  }

  archiveConversation(conversationId) {
    fetch(`/messages/archive/${conversationId}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
      },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.showNotification('Conversation archived', 'success');
          setTimeout(() => window.location.href = '/messages/inbox', 1000);
        }
      })
      .catch((err) => console.error('Error archiving conversation:', err));
  }

  unarchiveConversation(conversationId) {
    fetch(`/messages/unarchive/${conversationId}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
      },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.showNotification('Conversation unarchived', 'success');
          setTimeout(() => window.location.reload(), 1000);
        }
      })
      .catch((err) => console.error('Error unarchiving conversation:', err));
  }

  // ==================== TYPING INDICATORS ====================

  startTyping() {
    if (!this.isTyping && this.socket && this.currentConversationId) {
      this.isTyping = true;
      this.socket.emit('typing', { conversation_id: this.currentConversationId });
    }

    // Reset typing timeout
    clearTimeout(this.typingTimeout);
    this.typingTimeout = setTimeout(() => this.stopTyping(), 2000);
  }

  stopTyping() {
    if (this.isTyping && this.socket && this.currentConversationId) {
      this.isTyping = false;
      this.socket.emit('stop_typing', {
        conversation_id: this.currentConversationId,
      });
    }
    clearTimeout(this.typingTimeout);
  }

  showTypingIndicator(data) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    // Don't show for own user
    if (data.user_id === this.getCurrentUserId()) return;

    // Remove existing typing indicator
    const existing = document.querySelector('.typing-indicator');
    if (existing) existing.remove();

    const typingEl = document.createElement('div');
    typingEl.className = 'message-bubble other animate-fade-in';
    typingEl.innerHTML = `
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    `;

    chatMessages.appendChild(typingEl);
    this.scrollToBottom();
  }

  hideTypingIndicator(data) {
    const typingEl = document.querySelector('.typing-indicator');
    if (typingEl) {
      typingEl.parentElement.remove();
    }
  }

  // ==================== UI UTILITIES ====================

  showMessageMenu(messageId) {
    const menuHTML = `
      <div class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-hard z-10 animate-scale-in">
        <button class="w-full text-left px-4 py-2 hover:bg-gray-100 text-sm transition" 
                onclick="messagingApp.deleteMessage(${messageId})">
          <i class="fas fa-trash mr-2 text-red-500"></i> Delete
        </button>
        <button class="w-full text-left px-4 py-2 hover:bg-gray-100 text-sm transition" 
                onclick="messagingApp.copyToClipboard('message-${messageId}')">
          <i class="fas fa-copy mr-2 text-blue-500"></i> Copy
        </button>
      </div>
    `;
    // Implementation depends on your menu positioning needs
  }

  showNotification(message, type = 'info') {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 px-4 py-3 rounded-lg text-white animate-slide-in-down z-50 ${
      type === 'success'
        ? 'bg-green-500'
        : type === 'error'
          ? 'bg-red-500'
          : 'bg-blue-500'
    }`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('animate-fade-out');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  scrollToBottom() {
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
      // Use requestAnimationFrame for smooth scrolling
      requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
      });
    }
  }

  updateConversationPreview(messageData) {
    const convItem = document.querySelector(
      `[data-conversation-id="${messageData.conversation_id}"]`
    );
    if (convItem) {
      const preview = convItem.querySelector('.conversation-preview');
      if (preview) {
        const text = messageData.content.substring(0, 50);
        preview.textContent =
          text.length > 50 ? text + '...' : text;
        preview.classList.add('unread');
      }
    }
  }

  escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    };
    return text.replace(/[&<>"']/g, (m) => map[m]);
  }

  copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      const text = element.textContent;
      navigator.clipboard.writeText(text).then(() => {
        this.showNotification('Copied to clipboard', 'success');
      });
    }
  }

  getCSRFToken() {
    return (
      document.querySelector('meta[name="csrf-token"]')?.content || ''
    );
  }

  getCurrentUserId() {
    return document.querySelector('[data-current-user-id]')?.dataset
      .currentUserId || null;
  }

  // ==================== INITIALIZATION ====================

  attachEventListeners() {
    // Message textarea auto-grow
    const textarea = document.querySelector('.message-textarea');
    if (textarea) {
      textarea.addEventListener('input', (e) => {
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
        this.startTyping();
      });

      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }

    // Send button
    const sendBtn = document.querySelector('.send-button');
    if (sendBtn) {
      sendBtn.addEventListener('click', () => this.sendMessage());
    }

    // Conversation items
    document.querySelectorAll('.conversation-item').forEach((item) => {
      item.addEventListener('click', (e) => {
        const conversationId = item.dataset.conversationId;
        if (conversationId) {
          window.location.href = `/messages/conversation/${conversationId}`;
        }
      });
    });
  }

  loadInitialData() {
    // Load unread count
    fetch('/messages/api/unread-count')
      .then((res) => res.json())
      .then((data) => {
        this.unreadCount = data.unread_count;
        this.updateUnreadBadge();
      })
      .catch((err) => console.error('Error loading unread count:', err));
  }

  updateUnreadBadge() {
    const badge = document.querySelector('.unread-badge');
    const navbarBadge = document.querySelector('#unread-msg-badge');
    
    if (badge) {
      if (this.unreadCount > 0) {
        badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
        badge.style.display = 'inline-flex';
      } else {
        badge.style.display = 'none';
      }
    }
    
    // Update navbar badge
    if (navbarBadge) {
      if (this.unreadCount > 0) {
        navbarBadge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
        navbarBadge.style.display = 'inline-block';
      } else {
        navbarBadge.style.display = 'none';
      }
    }
  }

  incrementUnreadCount() {
    this.unreadCount++;
    this.updateUnreadBadge();
  }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.messagingApp = new MessagingApp();
});
