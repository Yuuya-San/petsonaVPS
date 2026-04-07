/**
 * Navbar Socket.IO Manager for Live Message & Notification Updates
 * Handles real-time updates to message badges and indicators without page refresh
 */

class NavbarSocketManager {
  constructor() {
    this.socket = null;
    this.messageCache = new Map(); // conversation_id -> message data
    this.initialized = false;
    this.init();
  }

  /**
   * Initialize Socket.IO connection for navbar updates
   */
  init() {
    try {
      // Check if Socket.IO library is available
      if (typeof io === 'undefined') {
        console.warn('⚠️ Socket.IO client library not loaded');
        return;
      }

      // Reuse existing socket or create new one
      if (window.navbarSocket) {
        this.socket = window.navbarSocket;
      } else {
        this.socket = io({
          reconnection: true,
          reconnectionDelay: 1000,
          reconnectionDelayMax: 5000,
          reconnectionAttempts: 5
        });
        window.navbarSocket = this.socket;
      }

      this.setupEventHandlers();
      this.initializeMessageItems();
      this.initialized = true;
      console.log('✅ Navbar Socket Manager initialized');
    } catch (error) {
      console.error('❌ Error initializing Navbar Socket Manager:', error);
    }
  }

  /**
   * Initialize message items with data attributes for tracking
   */
  initializeMessageItems() {
    const scrollContainer = document.querySelector('.messages-scroll-container');
    if (!scrollContainer) return;

    const messageItems = scrollContainer.querySelectorAll('.message-item');
    messageItems.forEach(item => {
      const href = item.getAttribute('href');
      const match = href.match(/conversation\/(\d+)/);
      if (match) {
        const conversationId = match[1];
        item.setAttribute('data-conversation-id', conversationId);
        
        // Get current unread count from indicator
        const indicator = item.querySelector('.new-message-indicator');
        if (indicator && indicator.textContent) {
          const count = parseInt(indicator.textContent.replace('+', '')) || 0;
          this.messageCache.set(conversationId, count);
        }
      }
    });
  }

  /**
   * Setup Socket.IO event handlers for navbar
   */
  setupEventHandlers() {
    if (!this.socket) return;

    // Listen for unread message count updates
    this.socket.on('message_unread_count_update', (data) => {
      console.log('📬 Message unread count update:', data);
      this.updateUnreadBadge(data.unread_count);
    });

    // Listen for new message navbar updates
    this.socket.on('navbar_message_update', (data) => {
      console.log('💬 Navbar message update:', data);
      this.updateMessageDropdown(data);
    });

    // Listen for message read updates
    this.socket.on('message_read', (data) => {
      console.log('✓ Message read:', data);
      this.handleMessageRead(data);
    });

    // Connection established
    this.socket.on('connect', () => {
      console.log('🔗 Navbar Socket connected:', this.socket.id);
    });

    // Disconnection
    this.socket.on('disconnect', () => {
      console.log('🔌 Navbar Socket disconnected');
    });

    // Reconnection
    this.socket.on('reconnect', () => {
      console.log('🔄 Navbar Socket reconnected');
      this.refreshNavbarData();
    });

    // Error handling
    this.socket.on('error', (error) => {
      console.error('⚠️ Socket error:', error);
    });

    // Setup click handlers for message items
    this.setupMessageItemClickHandlers();
  }

  /**
   * Setup click handlers for message items to clear indicators
   */
  setupMessageItemClickHandlers() {
    const scrollContainer = document.querySelector('.messages-scroll-container');
    if (!scrollContainer) return;

    // Add event delegation for dynamically added items
    scrollContainer.addEventListener('click', (e) => {
      const messageItem = e.target.closest('.message-item');
      if (!messageItem) return;

      // Extract conversation ID from href
      const href = messageItem.getAttribute('href');
      const match = href.match(/conversation\/(\d+)/);
      if (match) {
        const conversationId = match[1];
        // Clear the indicator after a short delay to allow navigation
        setTimeout(() => {
          this.clearConversationIndicator(conversationId);
        }, 100);
      }
    });

    // Also add direct click handlers to existing items
    const messageItems = scrollContainer.querySelectorAll('.message-item');
    messageItems.forEach(item => {
      item.addEventListener('click', (e) => {
        const href = item.getAttribute('href');
        const match = href.match(/conversation\/(\d+)/);
        if (match) {
          const conversationId = match[1];
          setTimeout(() => {
            this.clearConversationIndicator(conversationId);
          }, 100);
        }
      });
    });
  }

  /**
   * Update the unread message badge
   * @param {number} count - Unread message count
   */
  updateUnreadBadge(count) {
    const badge = document.getElementById('unread-msg-badge');
    if (!badge) return;

    if (count > 0) {
      badge.textContent = count < 10 ? count : '9+';
      badge.style.display = 'flex';
    } else {
      badge.textContent = '';
      badge.style.display = 'none';
    }
  }

  /**
   * Update message dropdown with new message
   * @param {Object} data - Message data {conversation_id, sender_id, sender_name, sender_avatar, message_preview}
   */
  updateMessageDropdown(data) {
    const scrollContainer = document.querySelector('.messages-scroll-container');
    if (!scrollContainer) {
      console.warn('Messages scroll container not found');
      return;
    }

    const conversationId = data.conversation_id;
    
    // Check if message item already exists for this conversation
    let messageItem = scrollContainer.querySelector(
      `a[href*="conversation/${conversationId}"]`
    );

    if (messageItem) {
      // Update existing conversation - increment unread count
      const indicator = messageItem.querySelector('.new-message-indicator');
      const currentCount = indicator ? parseInt(indicator.textContent.replace('+', '')) : 0;
      const newCount = currentCount + 1;
      
      // Update indicator with new count
      if (indicator) {
        indicator.textContent = newCount < 10 ? newCount : '9+';
      } else {
        // Create indicator if it doesn't exist
        const indicatorSpan = document.createElement('span');
        indicatorSpan.className = 'new-message-indicator';
        indicatorSpan.style.cssText = 'flex-shrink: 0; margin-left: 8px;';
        indicatorSpan.textContent = '1';
        const rightDiv = messageItem.querySelector('[style*="justify-content: space-between"]');
        if (rightDiv) {
          rightDiv.appendChild(indicatorSpan);
        }
      }
      
      // Ensure unread class is applied
      messageItem.classList.add('has-unread');
      
      // Update status text to unread
      const statusText = messageItem.querySelector('.message-status-read, .message-status-unread');
      if (statusText) {
        statusText.className = 'mb-0 message-status-unread';
        statusText.innerHTML = '<i class="fas fa-circle" style="font-size: 0.5rem; margin-right: 6px;"></i>You have new message';
      }
      
      // Move to top
      messageItem.remove();
      scrollContainer.insertBefore(messageItem, scrollContainer.firstChild);
    } else {
      // Add new conversation item at the top
      this.prependMessageItem(scrollContainer, data, 1);
    }

    // Scroll to top to show the new message
    scrollContainer.scrollTop = 0;
  }

  /**
   * Prepend a new message item to the scroll container
   * @param {HTMLElement} container - Container to append to
   * @param {Object} data - Message data
   * @param {number} unreadCount - Number of unread messages (default 1)
   */
  prependMessageItem(container, data, unreadCount = 1) {
    const indicatorHTML = unreadCount > 0 ? 
      `<span class="new-message-indicator" style="flex-shrink: 0; margin-left: 8px;">${unreadCount < 10 ? unreadCount : '9+'}</span>` 
      : '';
    
    const messageItemHTML = `
      <a href="/messages/conversation/${data.conversation_id}" class="dropdown-item message-item has-unread">
        <div class="d-flex align-items-center justify-content-between" style="width: 100%;">
          <div class="d-flex align-items-center" style="min-width: 0; flex: 1;">
            ${this.getAvatarHTML(data.sender_avatar, data.sender_name)}
            <div style="min-width: 0; flex: 1;">
              <p class="mb-0 text-dark font-weight-bold message-user-name">${this.escapeHtml(data.sender_name)}</p>
              <p class="mb-0 message-status-unread">
                <i class="fas fa-circle" style="font-size: 0.5rem; margin-right: 6px;"></i>You have new message
              </p>
            </div>
          </div>
          ${indicatorHTML}
        </div>
      </a>
    `;

    // Create temporary container to parse HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = messageItemHTML;
    const newItem = tempDiv.firstElementChild;

    // Insert at beginning of container
    if (container.firstChild) {
      container.insertBefore(newItem, container.firstChild);
    } else {
      container.appendChild(newItem);
    }

    // Add animation
    newItem.style.animation = 'fadeIn 0.3s ease-in-out';
  }

  /**
   * Get avatar HTML based on avatar URL and name
   * @param {string} avatarUrl - URL of avatar image
   * @param {string} name - User's name
   * @returns {string} HTML string for avatar
   */
  getAvatarHTML(avatarUrl, name) {
    if (avatarUrl) {
      return `<img src="${this.escapeHtml(avatarUrl)}" alt="${this.escapeHtml(name)}" class="img-circle mr-2" style="width: 36px; height: 36px; object-fit: cover; flex-shrink: 0;">`;
    } else {
      const firstLetter = name.charAt(0).toUpperCase();
      return `<div class="img-circle mr-2 d-flex align-items-center justify-content-center" style="width: 36px; height: 36px; background: #c8a2ff; color: white; font-weight: bold; flex-shrink: 0;">${firstLetter}</div>`;
    }
  }

  /**
   * Handle message read updates
   * @param {Object} data - Read notification data
   */
  handleMessageRead(data) {
    // Update message item's unread status if needed
    const messageItem = document.querySelector(
      `.message-item[data-message-id="${data.message_id}"]`
    );
    
    if (messageItem) {
      messageItem.classList.remove('has-unread');
      const indicator = messageItem.querySelector('.new-message-indicator');
      if (indicator) {
        indicator.style.display = 'none';
      }
      const statusText = messageItem.querySelector('.message-status-unread');
      if (statusText) {
        statusText.className = 'mb-0 message-status-read';
        statusText.textContent = 'No message yet';
      }
    }
  }

  /**
   * Refresh navbar data from server
   */
  refreshNavbarData() {
    console.log('🔄 Refreshing navbar data...');
    // Make AJAX call to fetch updated unread count
    fetch('/api/unread-count')
      .then(response => response.json())
      .then(data => {
        if (data.unread_count !== undefined) {
          this.updateUnreadBadge(data.unread_count);
        }
      })
      .catch(error => console.error('Error refreshing navbar:', error));
  }

  /**
   * Clear unread indicator for a specific conversation when clicked
   * @param {number} conversationId - Conversation ID
   */
  clearConversationIndicator(conversationId) {
    const scrollContainer = document.querySelector('.messages-scroll-container');
    if (!scrollContainer) return;
    
    const messageItem = scrollContainer.querySelector(
      `a[href*="conversation/${conversationId}"]`
    );
    
    if (messageItem) {
      // Remove unread class
      messageItem.classList.remove('has-unread');
      
      // Hide indicator
      const indicator = messageItem.querySelector('.new-message-indicator');
      if (indicator) {
        indicator.style.display = 'none';
      }
      
      // Update status text to read
      const statusText = messageItem.querySelector('.message-status-unread, .message-status-read');
      if (statusText) {
        statusText.className = 'mb-0 message-status-read';
        statusText.textContent = 'No message yet';
      }
    }
  }

  /**
   * Escape HTML special characters
   * @param {string} text - Text to escape
   * @returns {string} Escaped text
   */
  escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const manager = new NavbarSocketManager();
  window.navbarSocketManager = manager;
  
  // Initial setup - get current unread count from badge or API
  const badge = document.getElementById('unread-msg-badge');
  if (badge && badge.textContent) {
    const count = parseInt(badge.textContent.replace('+', '')) || 0;
    manager.updateUnreadBadge(count);
  }
});

// Add fadeIn animation if not exists
if (!document.querySelector('style[data-navbar-socket]')) {
  const style = document.createElement('style');
  style.setAttribute('data-navbar-socket', 'true');
  style.textContent = `
    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(-10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
  `;
  document.head.appendChild(style);
}
