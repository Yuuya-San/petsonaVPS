/**
 * Messaging Application - Optimized JavaScript
 * Fixed: Prevents UI lag and freezing during message sending
 */

class MessagingApp {
  constructor() {
    this.socket = null;
    this.currentConversationId = null;
    this.isTyping = false;
    this.typingTimeout = null;
    this.messageBuffer = [];
    this.unreadCount = 0;
    this.isSocketConnected = false;
    this.pendingMessageCallback = null;
    this.isSending = false;
    this.parseMediaHandler = null;
    this.pendingParseMessages = new Set();
    this.lastSendTime = 0; // For rate limiting rapid sends
    
    // Status tracking intervals
    this.heartbeatInterval = null;
    this.statusRefreshInterval = null;
    this.statusRequestInterval = null;
    
    this.init();
  }

  init() {
    this.connectSocket();
    this.attachEventListeners();
    this.loadInitialData();
    setTimeout(() => this.scrollToBottom(), 100);
    
    // Parse initial messages after initialization
    this.parseInitialMessages();
    
    // Cleanup on page leave
    window.addEventListener('beforeunload', () => {
      this.cleanup();
    });
  }

  cleanup() {
    // Clear all intervals
    if (this.heartbeatInterval) clearInterval(this.heartbeatInterval);
    if (this.statusRefreshInterval) clearInterval(this.statusRefreshInterval);
    if (this.statusRequestInterval) clearInterval(this.statusRequestInterval);
    
    // Mark user as inactive when leaving page
    if (this.socket && this.socket.connected && this.currentConversationId) {
      this.socket.emit('user_inactive', {
        conversation_id: this.currentConversationId
      });
      console.log('👋 Marked user as inactive on page leave');
    }
  }

  parseInitialMessages() {
    // Parse ALL message-parser elements on page load
    const allMessages = document.querySelectorAll('.message-parser');
    if (allMessages.length === 0) {
      console.log('📭 No messages to parse');
      return;
    }

    console.log(`🔍 Parsing ${allMessages.length} messages from database on initialization`);

    const parseMedia = (el) => {
      if (!el.dataset.parsed) {
        const messageEl = el.closest('.message-bubble');
        if (messageEl) {
          this.parseMediaInElement(messageEl);
          // Force visibility
          messageEl.style.opacity = '1';
          messageEl.style.display = 'flex';
          messageEl.style.visibility = 'visible';
        }
      }
    };

    // Use requestIdleCallback for non-blocking parsing
    if ('requestIdleCallback' in window) {
      requestIdleCallback(() => {
        allMessages.forEach(parseMedia);
        console.log('✅ All database messages parsed and verified visible');
        
        // Verify all messages are visible
        const bubbles = document.querySelectorAll('.message-bubble');
        bubbles.forEach(b => {
          b.style.opacity = '1';
          b.style.display = 'flex';
          b.style.visibility = 'visible';
        });
      }, { timeout: 2000 });
    } else {
      setTimeout(() => {
        allMessages.forEach(parseMedia);
        console.log('✅ All database messages parsed and verified visible');
        
        // Verify all messages are visible
        const bubbles = document.querySelectorAll('.message-bubble');
        bubbles.forEach(b => {
          b.style.opacity = '1';
          b.style.display = 'flex';
          b.style.visibility = 'visible';
        });
      }, 100);
    }
  }

  // ==================== SOCKET.IO SETUP ====================

  connectSocket() {
    // Wait for shared socket to be available
    const waitForSocket = setInterval(() => {
      if (window.sharedSocket) {
        clearInterval(waitForSocket);
        this.socket = window.sharedSocket;
        this.isSocketConnected = true;
        console.log('✅ Using shared socket connection');
        this.setupSocketEvents();
        
        // Join conversation room immediately
        const convId = this.getCurrentConversationId();
        if (convId && this.socket && this.socket.connected) {
          this.socket.emit('join_conversation', { conversation_id: convId });
          console.log(`📋 Joined conversation room: ${convId}`);
        }
      }
    }, 50);

    // Fallback: create new socket after 2 seconds if shared socket doesn't exist
    setTimeout(() => {
      if (!window.sharedSocket && !this.socket) {
        clearInterval(waitForSocket);
        console.log('⚠️ Creating new socket instance (shared socket not available)');
        this.socket = io({
          upgrade: false,
          reconnection: true,
          reconnectionDelay: 1000,
          reconnectionDelayMax: 5000,
          reconnectionAttempts: 5,
        });
        this.setupSocketEvents();
      }
    }, 2000);
  }

  setupSocketEvents() {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      this.isSocketConnected = true;
      console.log('✅ Socket connected');
      // Join conversation room after socket connects - use fresh conversation ID from DOM
      const convId = this.getCurrentConversationId();
      if (convId) {
        this.socket.emit('join_conversation', { conversation_id: convId });
        console.log(`📋 Joined conversation room: ${convId}`);
      }
    });

    this.socket.on('new_message', (data) => {
      console.log('📨 Received new_message event:', data);
      this.handleNewMessage(data);
    });

    this.socket.on('navbar_message_update', (data) => {
      console.log('📣 Received navbar_message_update event:', data);
      this.handleNavbarMessageUpdate(data);
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

    this.socket.on('user_status_changed', (data) => {
      console.log('🟢 Received user_status_changed event:', data);
      this.updateUserStatus(data);
    });

    this.socket.on('user_status', (data) => {
      console.log('👤 Received user_status event:', data);
      this.updateUserStatus(data);
    });

    this.socket.on('disconnect', (reason) => {
      this.isSocketConnected = false;
      console.log('❌ Socket disconnected:', reason);
    });

    this.socket.on('connect_error', (error) => {
      console.error('❌ Socket connection error:', error);
    });
  }

  // ==================== MESSAGE HANDLING ====================

  handleNewMessage(messageData) {
    const currentUserId = parseInt(document.querySelector('[data-current-user-id]')?.dataset.currentUserId);
    const isOwnMessage = messageData.sender_id === currentUserId;
    
    // Check if message already exists by real ID
    const existingMessage = document.querySelector(`[data-message-id="${messageData.id}"]`);
    if (existingMessage) {
      console.log('✅ Message already in DOM, skipping duplicate:', messageData.id);
      return;
    }
    
    // For own messages, check if a temp message with same content exists
    if (isOwnMessage) {
      const tempMessages = document.querySelectorAll('[data-message-id^="temp-"]');
      for (const tempMsg of tempMessages) {
        const tempContent = tempMsg.querySelector('.message-text')?.textContent || '';
        // If temp message has same content and was sent recently, it's the same message
        if (tempContent === messageData.content) {
          console.log(`✅ Matched existing temp message to real ID ${messageData.id}`);
          tempMsg.setAttribute('data-message-id', messageData.id);
          tempMsg.setAttribute('data-sender-id', messageData.sender_id);
          
          // UPDATE TIMESTAMP AND STATUS immediately
          const timeEl = tempMsg.querySelector('.message-time');
          if (timeEl) {
            timeEl.innerHTML = `${messageData.created_at_formatted_full || messageData.created_at_formatted}<span class="message-status ml-2"><i class="fas fa-check text-gray-400"></i></span>`;
          }
          
          // Parse media for this message
          const parser = tempMsg.querySelector('.message-parser');
          if (parser && parser.innerHTML.includes('[')) {
            this.scheduleMediaParse(tempMsg);
          }
          return; // Don't add as new message
        }
      }
    }
    
    // Add new message to DOM
    this.addMessageToDOM(messageData, isOwnMessage);
    console.log(`📬 New message added from ${isOwnMessage ? 'self' : 'other'}: ${messageData.id}`);
    this.updateConversationPreview(messageData);
  }

  handleMessageRead(data) {
    const messageEl = document.querySelector(`[data-message-id="${data.message_id}"]`);
    if (messageEl) {
      const statusEl = messageEl.querySelector('.message-status');
      if (statusEl) {
        statusEl.innerHTML = '<i class="fas fa-check-double text-blue-300"></i>';
      }
    }
    
    // Also update the conversation preview in sidebar if this conversation has no more unread messages
    this.updateConversationReadStatus(data.conversation_id);
  }

  updateConversationReadStatus(conversationId) {
    const convItem = document.querySelector(`[data-conversation-id="${conversationId}"]`);
    if (convItem) {
      const previewEl = convItem.querySelector('.conversation-preview');
      if (previewEl) {
        // When messages are read, we should show the normal preview instead of "You have new message"
        // For now, we'll get the last message content from the current chat
        const chatMessages = document.querySelectorAll('.message-bubble');
        if (chatMessages.length > 0) {
          const lastMessage = chatMessages[chatMessages.length - 1];
          const messageText = lastMessage.querySelector('.message-text');
          if (messageText) {
            const content = messageText.textContent || '';
            previewEl.textContent = content.substring(0, 50) + (content.length > 50 ? '...' : '');
            previewEl.className = 'text-sm text-slate-500 truncate';
            
            // Remove unread badge
            const badgeEl = convItem.querySelector('.unread-badge');
            if (badgeEl) {
              badgeEl.remove();
            }
          }
        }
      }
    }
  }

  addMessageToDOM(messageData, isOwn = false) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    const messageEl = document.createElement('div');
    messageEl.className = `message-bubble ${isOwn ? 'own' : 'other'} animate-slide-in-up`;
    messageEl.setAttribute('data-message-id', messageData.id);
    messageEl.setAttribute('data-sender-id', messageData.sender_id);
    messageEl.setAttribute('data-needs-parse', 'true');

    const statusHTML = isOwn
      ? `<div class="message-status">
           <span class="status-icon status-delivered">
             <i class="fas fa-check text-gray-400"></i>
           </span>
         </div>`
      : '';

    // Get other user information for avatar
    const container = document.querySelector('.messaging-container');
    const otherUserName = container?.dataset.otherUserName || 'User';
    const otherUserPhoto = container?.dataset.otherUserPhoto || '';
    
    // Build avatar HTML for other user messages
    const avatarHTML = !isOwn ? `
      <div class="message-avatar-container">
        <div class="message-avatar">
          ${otherUserPhoto 
            ? `<img src="${this.escapeHtml(otherUserPhoto)}" alt="${this.escapeHtml(otherUserName)}" loading="lazy" class="avatar-img" onerror="console.log('Avatar image load failed')">` 
            : `<span class="text-xs font-bold">${otherUserName.charAt(0).toUpperCase()}</span>`}
        </div>
      </div>` : '';

    // Build sender name HTML for other user messages
    const senderNameHTML = !isOwn ? `<div class="message-sender-name">${this.escapeHtml(otherUserName)}</div>` : '';

    messageEl.innerHTML = `
      ${avatarHTML}
      <div class="message-content-wrapper">
        ${senderNameHTML}
        <div class="message-content">
          <div class="message-text message-parser"></div>
          <div class="message-time">${messageData.created_at_formatted_full || messageData.created_at_formatted}</div>
          ${statusHTML}
        </div>
      </div>
    `;

    // Set message content - store original content for parsing, not escaped
    const messageParser = messageEl.querySelector('.message-parser');
    if (messageParser) {
      console.log('📝 Setting message content:', messageData.content.substring(0, 100));
      // Store the original content for media parsing
      messageParser.dataset.originalContent = messageData.content;
      messageParser.textContent = messageData.content; // Display as text initially
    }

    if (isOwn) {
      const menuBtn = document.createElement('button');
      menuBtn.className = 'message-menu-btn text-slate-400 hover:text-slate-600 transition p-1';
      menuBtn.innerHTML = '<i class="fas fa-ellipsis-v text-xs"></i>';
      menuBtn.setAttribute('data-message-id', messageData.id);
      menuBtn.title = 'Message options';
      menuBtn.onclick = () => this.showMessageMenu(messageData.id);
      messageEl.appendChild(menuBtn);
    }

    chatMessages.appendChild(messageEl);
    
    // Explicitly ensure message stays visible (critical for persistence)
    messageEl.style.opacity = '1';
    messageEl.style.display = 'flex';
    messageEl.style.visibility = 'visible';
    
    // Schedule media parsing for this new message only
    this.scheduleMediaParse(messageEl);
    this.scrollToBottom();
  }

  // ==================== OPTIMIZED MEDIA PARSING ====================

  scheduleMediaParse(element) {
    // Use requestIdleCallback for deferred parsing
    if ('requestIdleCallback' in window) {
      requestIdleCallback(() => this.parseMediaInElement(element), { timeout: 500 });
    } else {
      // Fallback for browsers without requestIdleCallback
      setTimeout(() => this.parseMediaInElement(element), 50);
    }
  }

  parseMediaInElement(element) {
    const messageParser = element.querySelector('.message-parser');
    if (!messageParser || messageParser.dataset.parsed === 'true') return;

    try {
      // Use original content if available, otherwise use innerHTML
      let html = messageParser.dataset.originalContent || messageParser.innerHTML;
      const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'];
      const linkRegex = /\[([^\]]+)\]\(([^\)]+)\)/g;
      
      let match;
      let newHtml = '';
      let lastIndex = 0;
      let hasChanges = false;
      let mediaCount = 0;

      while ((match = linkRegex.exec(html)) !== null) {
        const beforeText = html.substring(lastIndex, match.index);
        // Escape the plain text part
        newHtml += this.escapeHtmlForDOM(beforeText);

        const filename = match[1];
        const url = match[2];
        const ext = url.split('.').pop().toLowerCase();

        console.log(`🔍 Found media link: [${filename}](${url}), ext: ${ext}`);

        if (imageExts.includes(ext)) {
          console.log(`✅ Recognized as image: ${filename}`);
          newHtml += `<div class="media-attachment image-attachment" style="margin: 8px 0;">
                      <img src="${this.escapeHtml(url)}" alt="${this.escapeHtml(filename)}" class="media-image" style="max-width: 100%; height: auto; border-radius: 8px; cursor: pointer;" onclick="openDownloadDialog('${this.escapeHtml(url)}', '${this.escapeHtml(filename)}', 'image')" onerror="console.error('Image failed to load: ${url}');">
                    </div>`;
          hasChanges = true;
          mediaCount++;
        } else {
          console.log(`✅ Recognized as file: ${filename}`);
          const fileIcon = this.getFileIcon(ext);
          newHtml += `<div class="media-attachment file-attachment" style="margin: 8px 0; padding: 12px; background: #f5f5f5; border-radius: 8px; display: flex; align-items: center; gap: 12px; cursor: pointer;" onclick="openDownloadDialog('${this.escapeHtml(url)}', '${this.escapeHtml(filename)}', 'file')">
                      <div class="file-icon-wrapper" style="flex-shrink: 0;">
                        <i class="fas ${fileIcon}" style="font-size: 20px; color: #666;"></i>
                      </div>
                      <div class="file-info" style="flex: 1;">
                        <div class="file-name" style="font-weight: 500; color: #333;">${this.escapeHtml(filename)}</div>
                        <div class="file-size" style="font-size: 12px; color: #999;">Click to download</div>
                      </div>
                      <div class="download-icon" style="flex-shrink: 0;">
                        <i class="fas fa-download" style="color: #666;"></i>
                      </div>
                    </div>`;
          hasChanges = true;
          mediaCount++;
        }

        lastIndex = linkRegex.lastIndex;
      }

      if (hasChanges) {
        // Escape remaining text
        newHtml += this.escapeHtmlForDOM(html.substring(lastIndex));
        messageParser.innerHTML = newHtml;
        const messageId = element.getAttribute('data-message-id') || 'unknown';
        console.log(`✅ Parsed ${mediaCount} media items in message ${messageId}`);
      } else {
        // No media found, just escape the text
        const finalText = this.escapeHtmlForDOM(html);
        if (messageParser.innerHTML !== finalText) {
          messageParser.innerHTML = finalText;
        }
        console.log('✓ No media links found in message');
      }

      messageParser.dataset.parsed = 'true';
      // Ensure message remains visible after parsing
      element.style.opacity = '1';
      element.style.display = 'flex';
      element.style.visibility = 'visible';
    } catch (error) {
      console.error('❌ Error parsing media:', error);
      messageParser.dataset.parsed = 'true';
    }
  }

  // ==================== MESSAGE ACTIONS - OPTIMIZED ====================

  getCurrentConversationId() {
    // IMPORTANT: Look for the MAIN messaging container, not sidebar links!
    const containerEl = document.querySelector('.messaging-container');
    const convId = containerEl?.dataset.conversationId;
    
    if (convId) {
      const convIdInt = parseInt(convId);
      console.log(`🔍 Reading from .messaging-container data-conversation-id="${convId}" → int: ${convIdInt}`);
      this.currentConversationId = convIdInt;
      return convIdInt;
    }
    
    console.warn('⚠️ ERROR: No .messaging-container found in DOM!');
    return null;
  }

  sendMessage() {
    // Prevent rapid clicking - minimum 500ms between sends
    const now = Date.now();
    if (this.lastSendTime && (now - this.lastSendTime) < 500) {
      console.warn('⚠️ Send too fast, ignoring');
      return;
    }
    this.lastSendTime = now;

    if (this.isSending) {
      console.warn('⚠️ Already sending a message, ignoring duplicate click');
      return;
    }

    const textarea = document.querySelector('.message-textarea');
    const content = textarea.value.trim();
    const sendBtn = document.querySelector('.send-button');

    if (!content && !window.pendingPhotoFile) return;
    if (!this.getCurrentConversationId()) return;

    this.isSending = true;
    sendBtn.disabled = true;

    if (window.pendingPhotoFile) {
      this.uploadAndSendMessage(content, sendBtn, textarea);
      return;
    }

    if (!content) {
      this.isSending = false;
      sendBtn.disabled = false;
      return;
    }

    // Clear UI for text message
    textarea.value = '';
    textarea.style.height = 'auto';
    this.stopTyping();
    sendBtn.disabled = false;
    this.isSending = false;
    
    // Send without waiting
    this.sendTextMessageWithButton(content, sendBtn);
  }

  clearPreview() {
    const attachmentPreview = document.getElementById('attachment-preview');
    const photoPreview = document.getElementById('photo-preview-container');
    const photoUpload = document.getElementById('photo-upload');
    
    if (attachmentPreview) attachmentPreview.classList.add('hidden');
    if (photoPreview) photoPreview.classList.add('hidden');
    if (photoUpload) photoUpload.value = '';
    
    window.pendingPhotoFile = null;
  }

  sendTextMessageWithButton(content, sendBtn) {
    if (!content || !this.getCurrentConversationId()) return;

    // OPTIMISTIC UPDATE: Add message to DOM immediately (showing as pending/sending)
    const tempMessageId = `temp-${Date.now()}`;
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    const messageEl = document.createElement('div');
    messageEl.className = 'message-bubble own animate-slide-in-up';
    messageEl.setAttribute('data-message-id', tempMessageId);

    messageEl.innerHTML = `
      <div class="message-content-wrapper">
        <div class="message-content">
          <div class="message-text message-parser">${this.escapeHtml(content)}</div>
          <div class="message-time"></div>
        </div>
      </div>
    `;

    chatMessages.appendChild(messageEl);
    this.scrollToBottom();
    console.log('💭 Optimistic message added to DOM:', tempMessageId);

    // Create abort controller with 30 second timeout for message send
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 30000);

    // Send to server - always use fresh conversation ID from DOM
    const convIdToSendTo = this.getCurrentConversationId();
    const sendUrl = `/messages/send-message/${convIdToSendTo}`;
    console.log(`📤 SENDING MESSAGE`);
    console.log(`   URL: ${sendUrl}`);
    console.log(`   Content length: ${content.length}`);
    console.log(`   To conversation ID: ${convIdToSendTo}`);
    
    fetch(sendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCSRFToken(),
      },
      body: JSON.stringify({ content: content }),
      signal: abortController.signal,
    })
      .then(async (res) => {
        clearTimeout(timeoutId);
        console.log(`📩 Send response status: ${res.status}, headers:`, res.headers.get('content-type'));
        
        // Check if response is JSON
        const contentType = res.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const data = await res.json();
          return { status: res.status, data };
        } else {
          // Handle non-JSON responses (like HTML error pages)
          const text = await res.text();
          return { status: res.status, data: { success: false, error: `Server error (${res.status}): ${text.substring(0, 100)}...` } };
        }
      })
      .then(({ status, data }) => {
        console.log(`📩 Server response:`, data);
        
        const messageEl = document.querySelector(`[data-message-id="${tempMessageId}"]`);
        if (!messageEl) {
          console.warn('⚠️ Optimistic message element not found:', tempMessageId);
          // Try to find if it was already updated by socket event
          if (data.success && data.message) {
            const realMessageEl = document.querySelector(`[data-message-id="${data.message.id}"]`);
            if (realMessageEl) {
              console.log('✅ Message already exists with real ID, skipping update');
              return;
            }
          }
          return;
        }

        if (data.success && status === 200) {
          console.log('✅ Message confirmed by server:', data.message.id);
          console.log(`Updating temp ID [${tempMessageId}] → real ID [${data.message.id}]`);
          
          // Update message element with server data
          messageEl.setAttribute('data-message-id', data.message.id);
          messageEl.setAttribute('data-sender-id', data.message.sender_id);
          messageEl.style.opacity = '1';
          messageEl.style.display = 'flex';
          messageEl.style.visibility = 'visible';
          
          const timeEl = messageEl.querySelector('.message-time');
          const statusEl = messageEl.querySelector('.message-status');
          
          if (timeEl) {
            // Replace sending status with actual time
            timeEl.innerHTML = `${data.message.created_at_formatted_full || data.message.created_at_formatted}<span class="message-status ml-2"><i class="fas fa-check text-gray-400"></i></span>`;
          }
          if (statusEl) {
            // Remove the empty status element
            statusEl.remove();
          }

          // Parse media if any
          const messageParser = messageEl.querySelector('.message-parser');
          if (messageParser && messageParser.innerHTML.includes('[')) {
            console.log('🖼️ Parsing media in message:', messageEl.getAttribute('data-message-id'));
            this.scheduleMediaParse(messageEl);
          }
          
          // Ensure message stays visible and does not fade
          messageEl.classList.remove('loading-message', 'failed-message');
          messageEl.style.opacity = '1';
        } else {
          console.error('❌ Server rejected message:', data.error);
          
          // Handle rate limiting with retry
          if (status === 429) {
            console.log('⏳ Rate limited, will retry message:', tempMessageId);
            this.retryMessageWithBackoff(tempMessageId, content, 1);
            return;
          }
          
          messageEl.classList.add('failed-message');
          const timeEl = messageEl.querySelector('.message-time');
          if (timeEl) {
            timeEl.innerHTML = `<span class="text-red-500 text-xs">Failed - <span class="cursor-pointer hover:underline" onclick="messagingApp.retryMessage('${tempMessageId}')">retry</span></span>`;
          }
          this.showNotification(data.error || 'Failed to send', 'error');
        }
      })
      .catch((err) => {
        clearTimeout(timeoutId);
        console.error('❌ Send error:', err.message);
        
        const messageEl = document.querySelector(`[data-message-id="${tempMessageId}"]`);
        if (messageEl) {
          messageEl.classList.add('failed-message');
          const timeEl = messageEl.querySelector('.message-time');
          if (timeEl) {
            if (err.name === 'AbortError') {
              timeEl.innerHTML = `<span class="text-red-500 text-xs">Timeout - <span class="cursor-pointer hover:underline" onclick="messagingApp.retryMessage('${tempMessageId}')">retry</span></span>`;
              this.showNotification('❌ Message send timed out - check your connection', 'warning');
            } else {
              timeEl.innerHTML = `<span class="text-red-500 text-xs">Network error - <span class="cursor-pointer hover:underline" onclick="messagingApp.retryMessage('${tempMessageId}')">retry</span></span>`;
              this.showNotification('❌ Network error sending message', 'warning');
            }
          }
        }
      })
      .finally(() => {
        this.isSending = false;
        const sendBtn = document.querySelector('.send-button');
        if (sendBtn) sendBtn.disabled = false;
      });
  }

  retryMessage(tempMessageId) {
    console.log('🔄 Retrying message:', tempMessageId);
    const messageEl = document.querySelector(`[data-message-id="${tempMessageId}"]`);
    if (!messageEl) return;

    const textEl = messageEl.querySelector('.message-text');
    const content = textEl ? textEl.textContent.trim() : '';
    if (!content) {
      console.error('❌ No content to retry');
      return;
    }

    // Reset message to sending state
    messageEl.classList.remove('failed-message');
    const timeEl = messageEl.querySelector('.message-time');
    if (timeEl) {
      timeEl.innerHTML = `<span style="display:flex; align-items:center; gap:6px; font-size:0.75rem;">
        <span>retrying...</span>
        <div class="sending-spinner">
          <div class="spinner-dot"></div>
          <div class="spinner-dot"></div>
          <div class="spinner-dot"></div>
        </div>
      </span>`;
    }

    // Retry the send
    this.sendTextMessageWithButton(content, document.querySelector('.send-button'));
  }

  retryMessageWithBackoff(tempMessageId, content, attemptNumber = 1) {
    const maxAttempts = 3;
    const baseDelay = 2000; // 2 seconds
    const delay = baseDelay * Math.pow(2, attemptNumber - 1); // Exponential backoff

    console.log(`⏳ Scheduling retry ${attemptNumber}/${maxAttempts} for message ${tempMessageId} in ${delay}ms`);

    setTimeout(() => {
      const messageEl = document.querySelector(`[data-message-id="${tempMessageId}"]`);
      if (!messageEl) {
        console.log('⚠️ Message element no longer exists, cancelling retry');
        return;
      }

      // Update UI to show retry attempt
      messageEl.classList.remove('failed-message');
      const timeEl = messageEl.querySelector('.message-time');
      if (timeEl) {
        timeEl.innerHTML = `<span style="display:flex; align-items:center; gap:6px; font-size:0.75rem;">
          <span>retrying (${attemptNumber}/${maxAttempts})...</span>
          <div class="sending-spinner">
            <div class="spinner-dot"></div>
            <div class="spinner-dot"></div>
            <div class="spinner-dot"></div>
          </div>
        </span>`;
      }

      // Attempt to resend
      this.sendTextMessageWithRetry(content, tempMessageId, attemptNumber + 1);
    }, delay);
  }

  sendTextMessageWithRetry(content, tempMessageId, nextAttemptNumber = 1) {
    const convIdToSendTo = this.getCurrentConversationId();
    const sendUrl = `/messages/send-message/${convIdToSendTo}`;

    console.log(`🔄 RETRY ATTEMPT: Sending message ${tempMessageId} to ${sendUrl}`);

    fetch(sendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCSRFToken(),
      },
      body: JSON.stringify({ content: content }),
    })
      .then(async (res) => {
        console.log(`📩 Retry response status: ${res.status}`);
        
        // Check if response is JSON
        const contentType = res.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const data = await res.json();
          return { status: res.status, data };
        } else {
          // Handle non-JSON responses
          const text = await res.text();
          return { status: res.status, data: { success: false, error: `Server error (${res.status}): ${text.substring(0, 100)}...` } };
        }
      })
      .then(({ status, data }) => {
        const messageEl = document.querySelector(`[data-message-id="${tempMessageId}"]`);
        if (!messageEl) return;

        if (data.success && status === 200) {
          console.log('✅ Retry successful:', data.message.id);
          
          // Update message element with server data
          messageEl.setAttribute('data-message-id', data.message.id);
          messageEl.setAttribute('data-sender-id', data.message.sender_id);
          messageEl.classList.remove('failed-message', 'loading-message');
          messageEl.style.opacity = '1';
          
          const timeEl = messageEl.querySelector('.message-time');
          if (timeEl) {
            timeEl.innerHTML = `${data.message.created_at_formatted_full || data.message.created_at_formatted}<span class="message-status ml-2"><i class="fas fa-check text-gray-400"></i></span>`;
          }

          // Parse media if any
          const messageParser = messageEl.querySelector('.message-parser');
          if (messageParser && messageParser.innerHTML.includes('[')) {
            this.scheduleMediaParse(messageEl);
          }

          this.showNotification('✅ Message sent successfully', 'success');
        } else if (status === 429 && nextAttemptNumber <= 3) {
          console.log(`⏳ Rate limited again, retrying (${nextAttemptNumber}/3)...`);
          this.retryMessageWithBackoff(tempMessageId, content, nextAttemptNumber);
        } else {
          console.error('❌ Retry failed:', data.error);
          messageEl.classList.add('failed-message');
          const timeEl = messageEl.querySelector('.message-time');
          if (timeEl) {
            timeEl.innerHTML = `<span class="text-red-500 text-xs">Failed after retries - <span class="cursor-pointer hover:underline" onclick="messagingApp.retryMessage('${tempMessageId}')">retry</span></span>`;
          }
          this.showNotification(data.error || 'Failed to send after retries', 'error');
        }
      })
      .catch((err) => {
        console.error('❌ Retry network error:', err);
        const messageEl = document.querySelector(`[data-message-id="${tempMessageId}"]`);
        if (messageEl && nextAttemptNumber <= 3) {
          this.retryMessageWithBackoff(tempMessageId, content, nextAttemptNumber);
        } else if (messageEl) {
          messageEl.classList.add('failed-message');
          const timeEl = messageEl.querySelector('.message-time');
          if (timeEl) {
            timeEl.innerHTML = `<span class="text-red-500 text-xs">Network error - <span class="cursor-pointer hover:underline" onclick="messagingApp.retryMessage('${tempMessageId}')">retry</span></span>`;
          }
          this.showNotification('❌ Network error - check your connection', 'error');
        }
      });
  }

  addLoadingMessage(content) {
    const chatMessages = document.querySelector('.chat-messages');
    const messageEl = document.createElement('div');
    const tempId = `temp-${Date.now()}`;

    messageEl.className = `message-bubble own animate-slide-in-up loading-message`;
    messageEl.setAttribute('data-message-id', tempId);

    messageEl.innerHTML = `
      <div class="message-content-wrapper">
        <div class="message-content">
          <div class="message-text">${this.escapeHtml(content)}</div>
          <div class="message-time" style="display:flex; align-items:center; gap:8px;">
            <span style="font-size: 0.75rem; color: #ca8a04;">Uploading...</span>
            <div class="sending-spinner">
              <div class="spinner-dot"></div>
              <div class="spinner-dot"></div>
              <div class="spinner-dot"></div>
            </div>
          </div>
        </div>
      </div>
    `;

    chatMessages.appendChild(messageEl);
    this.scrollToBottom();
    return tempId;
  }

  uploadAndSendMessage(textContent, sendBtn, textarea) {
    // Clear UI immediately for file uploads
    const textareaEl = textarea || document.querySelector('.message-textarea');
    if (textareaEl) {
      textareaEl.value = '';
      textareaEl.style.height = 'auto';
    }
    this.stopTyping();
    
    // Get file objects BEFORE clearing preview
    const pendingPhoto = window.pendingPhotoFile ? { name: window.pendingPhotoFile.name, file: window.pendingPhotoFile } : null;
    const pendingFile = window.pendingFileObject ? { name: window.pendingFileObject.name, file: window.pendingFileObject } : null;
    
    this.clearPreview();

    const uploads = [];

    if (pendingPhoto) {
      console.log('📷 Uploading photo:', pendingPhoto.name);
      const formData = new FormData();
      formData.append('file', pendingPhoto.file);
      formData.append('type', 'photo');
      uploads.push(this.uploadFileInternal(formData, 'photo'));
    }

    if (uploads.length === 0) {
      console.log('✅ No files to upload, sending text only');
      this.isSending = false;
      sendBtn.disabled = false;
      if (!textContent.trim()) {
        this.showNotification('⚠️ Please enter a message or attach an image', 'warning');
        return;
      }
      this.sendTextMessageWithButton(textContent, sendBtn);
      return;
    }

    console.log(`⏳ Uploading ${uploads.length} image(s)...`);
    
    Promise.all(uploads)
      .then((results) => {
        console.log('✅ All images uploaded:', results);
        let finalContent = textContent || ''; // Start with text content
        
        // Add image references
        results.forEach((file) => {
          if (file && file.filename && file.url) {
            if (finalContent) finalContent += '\n'; // Add newline if there's existing content
            finalContent += `[${file.filename}](${file.url})`;
          }
        });
        
        // Ensure we have content to send
        if (!finalContent || !finalContent.trim()) {
          console.error('❌ No content to send after image upload');
          this.showNotification('❌ Error: No content or images to send', 'error');
          this.isSending = false;
          sendBtn.disabled = false;
          return;
        }
        
        console.log('📨 Sending message with images to database, content length:', finalContent.length);
        
        // Send the actual message with image references
        this.isSending = true;
        sendBtn.disabled = true;
        this.sendTextMessageWithButton(finalContent, sendBtn);
      })
      .catch((err) => {
        console.error('❌ Upload error:', err);
        this.isSending = false;
        sendBtn.disabled = false;
        
        // Provide specific error messages
        const errorMsg = err.message || 'Unknown error';
        console.error('Error details:', errorMsg);
        
        if (errorMsg.includes('timed out')) {
          this.showNotification('❌ File upload too slow - check your internet connection', 'error');
        } else if (errorMsg.includes('Network')) {
          this.showNotification('❌ Network error - check your connection', 'error');
        } else if (errorMsg.includes('Invalid file type')) {
          this.showNotification('❌ File type not allowed', 'error');
        } else if (errorMsg.includes('exceeds maximum')) {
          this.showNotification('❌ File is too large', 'error');
        } else if (errorMsg.includes('No file')) {
          this.showNotification('❌ Server error: file not received', 'error');
        } else {
          this.showNotification('❌ ' + errorMsg, 'error');
        }
      })
      .finally(() => {
        this.isSending = false;
        sendBtn.disabled = false;
      });
  }

  uploadFileInternal(formData, fileType = 'file') {
    const convId = document.querySelector('[data-conversation-id]')?.dataset.conversationId;
    if (!convId) {
      console.error('❌ No conversation ID found');
      return Promise.reject(new Error('No conversation ID'));
    }

    // Create abort controller with 120 second timeout for larger files
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => {
      console.error('⏱️ File upload timeout - aborting after 120 seconds');
      abortController.abort();
    }, 120000);

    const csrfToken = this.getCSRFToken();
    console.log(`📤 Uploading ${fileType} to conversation ${convId}`);
    console.log(`   CSRF Token: ${csrfToken ? '✅ Present' : '❌ Missing'}`);

    const headers = {};
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }

    return fetch(`/messages/upload-file/${convId}`, {
      method: 'POST',
      body: formData,
      headers: headers,
      signal: abortController.signal,
    })
      .then((res) => {
        clearTimeout(timeoutId);
        console.log(`📥 Upload response status: ${res.status}`);
        return res.json().then(data => ({ status: res.status, data }));
      })
      .then(({ status, data }) => {
        if (status === 200 && data.success) {
          console.log('✅ File upload successful:', { filename: data.filename, url: data.url });
          return { filename: data.filename, url: data.url };
        }
        // Extract error message from server response
        const errorMsg = data.error || 'Upload failed';
        console.error('❌ Upload failed with error:', errorMsg);
        throw new Error(errorMsg);
      })
      .catch((err) => {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError') {
          console.error('⏱️ File upload timed out');
          throw new Error('File upload timed out - check your internet connection');
        }
        console.error('❌ Upload error:', err.message);
        throw err;
      });
  }

  // ==================== CONVERSATION ACTIONS ====================

  blockUser(conversationId) {
    if (!confirm('Block this user? You won\'t receive messages from them.')) return;

    fetch(`/messages/block-user/${conversationId}`, {
      method: 'POST',
      headers: { 'X-CSRFToken': this.getCSRFToken() },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.showNotification('User blocked', 'success');
          location.reload();
        }
      })
      .catch((err) => console.error('Block error:', err));
  }

  unblockUser(conversationId) {
    fetch(`/messages/unblock-user/${conversationId}`, {
      method: 'POST',
      headers: { 'X-CSRFToken': this.getCSRFToken() },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.showNotification('User unblocked', 'success');
          location.reload();
        }
      })
      .catch((err) => console.error('Unblock error:', err));
  }

  archiveConversation(conversationId) {
    fetch(`/messages/archive/${conversationId}`, {
      method: 'POST',
      headers: { 'X-CSRFToken': this.getCSRFToken() },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.showNotification('Conversation archived', 'success');
          setTimeout(() => (location.href = '/messages'), 500);
        }
      })
      .catch((err) => console.error('Archive error:', err));
  }

  unarchiveConversation(conversationId) {
    fetch(`/messages/unarchive/${conversationId}`, {
      method: 'POST',
      headers: { 'X-CSRFToken': this.getCSRFToken() },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          this.showNotification('Conversation restored', 'success');
        }
      })
      .catch((err) => console.error('Unarchive error:', err));
  }

  deleteMessage(messageId) {
    if (!confirm('Delete this message?')) return;

    fetch(`/messages/delete-message/${messageId}`, {
      method: 'POST',
      headers: { 'X-CSRFToken': this.getCSRFToken() },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
          if (messageEl) messageEl.remove();
          this.showNotification('Message deleted', 'success');
        }
      })
      .catch((err) => console.error('Delete error:', err));
  }

  // ==================== TYPING INDICATORS ====================

  startTyping() {
    const convId = this.getCurrentConversationId();
    if (!this.isTyping && this.socket && convId) {
      this.isTyping = true;
      this.socket.emit('typing', { conversation_id: convId });
    }

    clearTimeout(this.typingTimeout);
    this.typingTimeout = setTimeout(() => this.stopTyping(), 2000);
  }

  stopTyping() {
    const convId = this.getCurrentConversationId();
    if (this.isTyping && this.socket && convId) {
      this.isTyping = false;
      this.socket.emit('stop_typing', { conversation_id: convId });
    }
    clearTimeout(this.typingTimeout);
  }

  showTypingIndicator(data) {
    const typingContainer = document.getElementById('typing-container');
    if (!typingContainer || data.user_id === this.getCurrentUserId()) return;

    // Check if already showing
    if (typingContainer.classList.contains('active')) return;

    typingContainer.classList.remove('hidden');
    typingContainer.classList.add('active');
    this.scrollToBottom();
    console.log('⌨️ User is typing...');
  }

  hideTypingIndicator(data) {
    const typingContainer = document.getElementById('typing-container');
    if (typingContainer) {
      typingContainer.classList.remove('active');
      typingContainer.classList.add('hidden');
    }
    console.log('✋ User stopped typing');
  }

  updateUserStatus(statusData) {
    try {
      const statusEl = document.querySelector('.user-status-indicator');
      const statusTextEl = document.querySelector('.user-status-text');
      
      if (!statusEl || !statusTextEl) {
        console.log('⚠️ Status elements not found');
        return;
      }

      const { is_online, timestamp } = statusData;
      
      let shouldShowActive = false;
      
      // SIMPLE RULE: Show "Active now" ONLY if BOTH true:
      // 1. is_online = true (user has activity/connection)
      // 2. timestamp < 5 minutes
      if (is_online && timestamp) {
        const lastSeenDate = new Date(timestamp);
        const now = new Date();
        const minutesDiff = (now - lastSeenDate) / (1000 * 60);
        
        console.log(`⏱️ Last seen: ${minutesDiff.toFixed(1)}m ago, is_online: ${is_online}`);
        
        if (minutesDiff < 5) {
          shouldShowActive = true;
        }
      }

      if (shouldShowActive) {
        // Show "Active now" - green indicator
        statusEl.classList.remove('bg-slate-300', 'bg-gray-400');
        statusEl.classList.add('bg-green-400', 'animate-pulse');
        statusTextEl.textContent = 'Active now';
        console.log(`🟢 ACTIVE NOW`);
      } else {
        // Show offline with time - gray indicator
        statusEl.classList.remove('bg-green-400', 'animate-pulse');
        statusEl.classList.add('bg-slate-300');
        
        if (timestamp) {
          statusTextEl.dataset.lastSeenTimestamp = timestamp;
          this.updateOfflineStatusText(statusTextEl, timestamp);
        } else {
          statusTextEl.textContent = 'Offline';
        }
        console.log(`⚫ OFFLINE`);
      }
      
    } catch (error) {
      console.error('❌ Error updating status:', error);
    }
  }

  updateOfflineStatusText(statusTextEl, timestamp) {
    // Update the offline status text with live time difference
    try {
      const lastSeenDate = new Date(timestamp);
      const now = new Date();
      const diffSeconds = Math.floor((now - lastSeenDate) / 1000);
      
      let displayText = '';
      
      if (diffSeconds < 60) {
        displayText = 'Just now';
      } else if (diffSeconds < 3600) {
        const minutes = Math.floor(diffSeconds / 60);
        displayText = minutes === 1 ? '1m ago' : `${minutes}m ago`;
      } else if (diffSeconds < 86400) {
        const hours = Math.floor(diffSeconds / 3600);
        displayText = hours === 1 ? '1h ago' : `${hours}h ago`;
      } else {
        const days = Math.floor(diffSeconds / 86400);
        displayText = days === 1 ? '1d ago' : `${days}d ago`;
      }
      
      statusTextEl.textContent = displayText;
    } catch (error) {
      console.error('❌ Error updating offline text:', error);
      statusTextEl.textContent = 'Offline';
    }
  }

  // ==================== UI UTILITIES ====================

  showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 px-4 py-3 rounded-lg text-white animate-slide-in-down z-50 ${
      type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500'
    }`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
  }

  scrollToBottom() {
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
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
      const previewEl = convItem.querySelector('.conversation-preview');
      if (previewEl) {
        const currentUserId = parseInt(document.querySelector('.messaging-container')?.dataset.currentUserId);
        const isFromOtherUser = messageData.sender_id !== currentUserId;

        if (isFromOtherUser) {
          previewEl.innerHTML = '<i class="fas fa-circle mr-2" style="font-size: 0.5rem;"></i>You have new message';
          previewEl.className = 'conversation-preview text-sm text-red-600 truncate';
          
          let badgeEl = convItem.querySelector('.unread-badge');
          if (!badgeEl) {
            const nameEl = convItem.querySelector('h4');
            if (nameEl) {
              badgeEl = document.createElement('span');
              badgeEl.className = 'bg-red-600 text-white text-xs font-bold rounded-full px-2 py-1 flex-shrink-0 unread-badge';
              badgeEl.textContent = '1';
              nameEl.parentNode.insertBefore(badgeEl, nameEl.nextSibling);
            }
          }
        } else {
          previewEl.textContent = messageData.content.substring(0, 50);
          previewEl.className = 'conversation-preview text-sm text-slate-500 truncate';
          
          const badgeEl = convItem.querySelector('.unread-badge');
          if (badgeEl) {
            badgeEl.remove();
          }
        }
      }
    }
  }

  handleNavbarMessageUpdate(data) {
    const convItem = document.querySelector(`[data-conversation-id="${data.conversation_id}"]`);
    if (!convItem) return;

    const previewEl = convItem.querySelector('.conversation-preview');
    if (!previewEl) return;

    previewEl.innerHTML = '<i class="fas fa-circle mr-2" style="font-size: 0.5rem;"></i>You have new message';
    previewEl.className = 'conversation-preview text-sm text-red-600 truncate';

    let badgeEl = convItem.querySelector('.unread-badge');
    if (!badgeEl) {
      const nameEl = convItem.querySelector('h4');
      if (nameEl) {
        badgeEl = document.createElement('span');
        badgeEl.className = 'bg-red-600 text-white text-xs font-bold rounded-full px-2 py-1 flex-shrink-0 unread-badge';
        nameEl.parentNode.insertBefore(badgeEl, nameEl.nextSibling);
      }
    }
    if (badgeEl) {
      badgeEl.textContent = '1';
    }
  }

  escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return text.replace(/[&<>"']/g, (m) => map[m]);
  }

  escapeHtmlForDOM(text) {
    // Same as escapeHtml but with a clearer name for DOM operations
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return text.replace(/[&<>"']/g, (m) => map[m]);
  }

  getFileIcon(ext) {
    const iconMap = {
      pdf: 'fa-file-pdf',
      doc: 'fa-file-word',
      docx: 'fa-file-word',
      xls: 'fa-file-excel',
      xlsx: 'fa-file-excel',
      ppt: 'fa-file-powerpoint',
      pptx: 'fa-file-powerpoint',
      txt: 'fa-file-text',
      zip: 'fa-file-archive',
      rar: 'fa-file-archive',
    };
    return iconMap[ext] || 'fa-file';
  }

  copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      navigator.clipboard.writeText(element.textContent);
      this.showNotification('Copied!', 'success');
    }
  }

  handlePhotoUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const validMimeTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!validMimeTypes.includes(file.type)) {
      this.showNotification('Invalid image format', 'error');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      this.showNotification('Image too large (max 5MB)', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      this.showPhotoPreview(e.target.result, file.name, file);
    };
    reader.readAsDataURL(file);
  }

  showPhotoPreview(dataUrl, filename, fileObject) {
    const previewContainer = document.getElementById('photo-preview-container');
    const previewImg = document.getElementById('photo-preview-img');
    const attachmentPreview = document.getElementById('attachment-preview');

    if (!previewContainer) return;

    previewImg.src = dataUrl;
    previewContainer.classList.remove('hidden');
    attachmentPreview.classList.remove('hidden');
    window.pendingPhotoFile = fileObject;
  }

  removePhotoPreview() {
    const previewContainer = document.getElementById('photo-preview-container');
    const attachmentPreview = document.getElementById('attachment-preview');
    const photoUpload = document.getElementById('photo-upload');

    if (previewContainer) previewContainer.classList.add('hidden');
    attachmentPreview.classList.add('hidden');

    photoUpload.value = '';
    window.pendingPhotoFile = null;
  }

  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  }

  getCSRFToken() {
    // Try multiple methods to get CSRF token
    let token = document.querySelector('meta[name="csrf-token"]')?.content;
    if (token) return token;
    
    // Fallback: check document.csrf_token (Flask-Talisman)
    if (window.csrf_token) return window.csrf_token;
    
    // Fallback: check form hidden input
    token = document.querySelector('input[name="csrf_token"]')?.value;
    if (token) return token;
    
    console.warn('⚠️ CSRF token not found!');
    return '';
  }

  getCurrentUserId() {
    return parseInt(document.querySelector('[data-current-user-id]')?.dataset.currentUserId);
  }

  showMessageMenu(messageId) {
    const menuHTML = `
      <div class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-hard z-10">
        <button onclick="messagingApp.deleteMessage(${messageId})" class="w-full text-left px-4 py-2 hover:bg-gray-100">
          <i class="fas fa-trash text-red-500"></i> Delete
        </button>
      </div>
    `;
  }

  // ==================== INITIALIZATION ====================

  attachEventListeners() {
    const textarea = document.querySelector('.message-textarea');
    const sendBtn = document.querySelector('.send-button');
    const photoBtn = document.getElementById('photo-btn');
    const photoUpload = document.getElementById('photo-upload');
    const removePhotoPreviewBtn = document.getElementById('remove-photo-preview');
    const photoPreviewContainer = document.getElementById('photo-preview-container');

    console.log('🔗 Attaching event listeners...');
    console.log(`  photoBtn: ${photoBtn ? '✅' : '❌'}`);
    console.log(`  photoUpload: ${photoUpload ? '✅' : '❌'}`);

    if (textarea) {
      textarea.addEventListener('input', () => this.startTyping());
      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }

    if (sendBtn) {
      sendBtn.addEventListener('click', () => this.sendMessage());
    }

    if (photoBtn) {
      photoBtn.addEventListener('click', () => {
        console.log('📷 Photo button clicked, triggering file input');
        photoUpload?.click();
      });
    }

    if (photoUpload) {
      photoUpload.addEventListener('change', (e) => {
        console.log('📸 Photo selected:', e.target.files[0]?.name);
        this.handlePhotoUpload(e);
      });
    }

    // Preview remove button handlers
    if (removePhotoPreviewBtn) {
      removePhotoPreviewBtn.addEventListener('click', () => this.removePhotoPreview());
    }

    // Preview click to view handlers
    if (photoPreviewContainer) {
      photoPreviewContainer.addEventListener('click', (e) => {
        if (e.target.id !== 'remove-photo-preview' && !e.target.closest('#remove-photo-preview')) {
          const img = photoPreviewContainer.querySelector('.preview-image');
          if (img && img.src) {
            openDownloadDialog(img.src, 'photo-preview.jpg', 'image');
          }
        }
      });
    }
  }

  loadInitialData() {
    const convId = document.querySelector('[data-conversation-id]')?.dataset.conversationId;
    if (convId) {
      this.currentConversationId = parseInt(convId);
      console.log(`📋 Current conversation ID: ${this.currentConversationId}`);
    }

    // Get other user ID
    const otherUserIdEl = document.querySelector('[data-other-user-id]');
    const otherUserId = otherUserIdEl ? parseInt(otherUserIdEl.dataset.otherUserId) : null;

    if (!otherUserId) {
      console.error('❌ Could not find other user ID');
      return;
    }

    // Request other user's current status immediately if socket is ready
    const requestStatus = () => {
      if (this.socket && this.socket.connected) {
        console.log(`👤 Requesting status for user ${otherUserId}...`);
        this.socket.emit('get_user_status', { user_id: otherUserId });
      } else {
        console.log('⏳ Socket not connected yet, retrying status request...');
        setTimeout(requestStatus, 300);
      }
    };

    requestStatus();

    // Notify server that user is online in this conversation
    const notifyOnline = () => {
      if (this.socket && this.socket.connected && this.currentConversationId) {
        this.socket.emit('user_online', {
          conversation_id: this.currentConversationId,
          other_user_id: otherUserId
        });
        console.log('🟢 Notified server user is online');
      } else {
        setTimeout(notifyOnline, 300);
      }
    };

    notifyOnline();

    // Set up activity tracking for online/offline status
    this.setupActivityTracking(otherUserId);

    // Set up frequent periodic heartbeats to keep user status fresh (every 20 seconds)
    this.heartbeatInterval = setInterval(() => {
      if (this.socket && this.socket.connected && this.currentConversationId) {
        this.socket.emit('user_online', {
          conversation_id: this.currentConversationId,
          other_user_id: otherUserId
        });
        console.log('💓 Heartbeat: User online');
      }
    }, 20000);

    // Set up frequent status text refresh for offline users (every 10 seconds)
    this.statusRefreshInterval = setInterval(() => {
      const statusTextEl = document.querySelector('.user-status-text');
      const statusEl = document.querySelector('.user-status-indicator');
      
      if (statusTextEl && statusTextEl.dataset.lastSeenTimestamp && !statusEl.classList.contains('status-online')) {
        this.updateOfflineStatusText(statusTextEl, statusTextEl.dataset.lastSeenTimestamp);
        console.log('🔄 Auto-refresh: Updated offline status text');
      }
    }, 10000);

    // Request status more frequently to ensure 5-minute offline threshold is properly detected (every 3 seconds)
    this.statusRequestInterval = setInterval(() => {
      if (this.socket && this.socket.connected && otherUserId) {
        this.socket.emit('get_user_status', { user_id: otherUserId });
        console.log('🔎 Auto-refresh: Requested latest status');
      }
    }, 3000);
  }

  setupActivityTracking(otherUserId) {
    // Set up tracking for user inactivity and online status
    let inactivityTimeout;
    const inactivityDuration = 3 * 60 * 1000; // 3 minutes for demo (normally 5)

    const resetActivityTimer = () => {
      clearTimeout(inactivityTimeout);

      // Notify server that user is active WITH MORE FREQUENCY
      if (this.socket && this.socket.connected && this.currentConversationId) {
        this.socket.emit('user_online', {
          conversation_id: this.currentConversationId,
          other_user_id: otherUserId
        });
      }

      // Set inactivity timer - shorter for faster detection
      inactivityTimeout = setTimeout(() => {
        console.log('⏱️ User idle for 3 minutes, marking as inactive');
        if (this.socket && this.socket.connected && this.currentConversationId) {
          this.socket.emit('user_inactive', {
            conversation_id: this.currentConversationId
          });
        }
      }, inactivityDuration);
    };

    // Track user activity with aggressive debouncing (500ms)
    let activityThrottle = false;
    const throttledActivity = () => {
      if (!activityThrottle) {
        resetActivityTimer();
        activityThrottle = true;
        setTimeout(() => { activityThrottle = false; }, 500); // More frequent checks
      }
    };

    document.addEventListener('mousemove', throttledActivity, true);
    document.addEventListener('keydown', throttledActivity, true);
    document.addEventListener('click', throttledActivity, true);
    document.addEventListener('scroll', throttledActivity, true);
    document.addEventListener('focus', throttledActivity, true);
    document.addEventListener('input', throttledActivity, true);

    // Track page visibility
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        console.log('📵 Page hidden, marking user as inactive');
        if (this.socket && this.socket.connected && this.currentConversationId) {
          this.socket.emit('user_inactive', {
            conversation_id: this.currentConversationId
          });
        }
        clearTimeout(inactivityTimeout);
      } else {
        console.log('📱 Page visible, marking user as online');
        resetActivityTimer();
      }
    });

    // Initialize the timer
    resetActivityTimer();
  }

}

// Global helper functions
function openDownloadDialog(url, filename, type) {
  const modal = document.createElement('div');
  modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
  
  const closeModal = () => {
    modal.remove();
  };

  modal.innerHTML = `
    <div class="bg-white rounded-lg p-6 max-w-sm w-11/12 flex flex-col gap-4">
      <div class="flex justify-between items-center mb-2">
        <h3 class="text-lg font-semibold text-gray-800">${type === 'image' ? 'View Image' : 'File Preview'}</h3>
        <button class="text-gray-500 hover:text-gray-700 text-2xl leading-none" style="background: none; border: none; cursor: pointer;">×</button>
      </div>
      <div class="flex-1 min-h-0">
        ${
          type === 'image'
            ? `<img src="${url.replace(/"/g, '&quot;')}" alt="${filename.replace(/"/g, '&quot;')}" class="w-full h-auto rounded object-contain">`
            : `<div class="text-center py-8 bg-gray-50 rounded flex flex-col items-center justify-center">
                <i class="fas fa-file text-4xl text-gray-400 mb-3"></i>
                <p class="text-sm font-medium text-gray-700 text-center break-words">${filename.replace(/"/g, '&quot;')}</p>
              </div>`
        }
      </div>
      <div class="flex flex-row gap-2 pt-2">
        <a href="${url.replace(/"/g, '&quot;')}" download class="flex-1 text-center bg-purple-600 hover:bg-purple-700 text-white font-medium py-2 rounded transition" style="text-decoration: none;">
          <i class="fas fa-download mr-2"></i>Download
        </a>
        <button class="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium py-2 rounded transition" style="background-color: #e5e7eb; cursor: pointer;">Close</button>
      </div>
    </div>
  `;

  // Close button in header
  const closeBtn = modal.querySelector('.flex.justify-between button');
  if (closeBtn) {
    closeBtn.addEventListener('click', closeModal);
  }

  // Close button in footer
  const footerCloseBtn = modal.querySelector('div.flex.flex-row button');
  if (footerCloseBtn) {
    footerCloseBtn.addEventListener('click', closeModal);
  }

  // Close when clicking on background
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeModal();
    }
  });

  document.body.appendChild(modal);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  console.log('🚀 Initializing MessagingApp on DOMContentLoaded...');
  window.messagingApp = new MessagingApp();
  
  console.log('✅ MessagingApp created. Socket status:', window.messagingApp.isSocketConnected);
  console.log('✅ Socket object:', window.messagingApp.socket ? 'Present' : 'Missing');

  // Parse ALL initial messages after a small delay to ensure DOM is ready
  setTimeout(() => {
    const allMessages = document.querySelectorAll('.message-parser');
    console.log(`🔍 Found ${allMessages.length} message-parser elements to parse`);
    
    allMessages.forEach((el) => {
      const messageEl = el.closest('.message-bubble');
      if (messageEl && !el.dataset.parsed) {
        messagingApp.parseMediaInElement(messageEl);
        // Ensure visibility after parsing
        messageEl.style.opacity = '1';
        messageEl.style.display = 'flex';
        messageEl.style.visibility = 'visible';
      }
    });
    
    // Final verification: Log all messages that should be visible
    const allBubbles = document.querySelectorAll('.message-bubble');
    console.log(`✅ Final message count: ${allBubbles.length} messages in DOM`);
    allBubbles.forEach((bubble, idx) => {
      const msgId = bubble.getAttribute('data-message-id');
      const isOwn = bubble.classList.contains('own') ? 'own' : 'other';
      const opacity = window.getComputedStyle(bubble).opacity;
      const display = window.getComputedStyle(bubble).display;
      console.log(`  [${idx + 1}] Message ${msgId} (${isOwn}) - opacity: ${opacity}, display: ${display}`);
    });
  }, 300);
});
