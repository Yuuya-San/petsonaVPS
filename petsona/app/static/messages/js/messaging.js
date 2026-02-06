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
    this.init();
  }

  init() {
    this.connectSocket();
    this.attachEventListeners();
    this.loadInitialData();
    setTimeout(() => this.scrollToBottom(), 100);
    
    // Parse initial messages after initialization
    this.parseInitialMessages();
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
    if (window.sharedSocket && window.sharedSocket.connected) {
      this.socket = window.sharedSocket;
      this.isSocketConnected = true;
    } else {
      this.socket = io({
        upgrade: false,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
      });
    }

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
            ? `<img src="${otherUserPhoto}" alt="${this.escapeHtml(otherUserName)}" loading="lazy" class="avatar-img" onerror="console.log('Avatar image load failed')">` 
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
          <div class="message-text message-parser">${messageData.content}</div>
          <div class="message-time">${messageData.created_at_formatted_full || messageData.created_at_formatted}</div>
          ${statusHTML}
        </div>
      </div>
    `;

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
      let html = messageParser.innerHTML;
      const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'];
      const linkRegex = /\[([^\]]+)\]\(([^\)]+)\)/g;
      
      let match;
      let newHtml = '';
      let lastIndex = 0;
      let hasChanges = false;

      while ((match = linkRegex.exec(html)) !== null) {
        const beforeText = html.substring(lastIndex, match.index);
        newHtml += beforeText;

        const filename = match[1];
        const url = match[2];
        const ext = url.split('.').pop().toLowerCase();

        if (imageExts.includes(ext)) {
          newHtml += `<div class="media-attachment image-attachment">
                      <img src="${this.escapeHtml(url)}" alt="${this.escapeHtml(filename)}" class="media-image" onclick="openDownloadDialog('${this.escapeHtml(url)}', '${this.escapeHtml(filename)}', 'image')" onerror="console.log('Image load failed: ${url}')">
                    </div>`;
          hasChanges = true;
        } else {
          const fileIcon = this.getFileIcon(ext);
          newHtml += `<div class="media-attachment file-attachment" onclick="openDownloadDialog('${this.escapeHtml(url)}', '${this.escapeHtml(filename)}', 'file')">
                      <div class="file-icon-wrapper">
                        <i class="fas ${fileIcon}"></i>
                      </div>
                      <div class="file-info">
                        <div class="file-name">${this.escapeHtml(filename)}</div>
                        <div class="file-size">Unknown</div>
                      </div>
                      <div class="download-icon">
                        <i class="fas fa-download"></i>
                      </div>
                    </div>`;
          hasChanges = true;
        }

        lastIndex = linkRegex.lastIndex;
      }

      if (hasChanges) {
        newHtml += html.substring(lastIndex);
        messageParser.innerHTML = newHtml;
        const messageId = element.getAttribute('data-message-id') || 'unknown';
        console.log('✅ Media parsed in message:', messageId);
      }

      messageParser.dataset.parsed = 'true';
      // Ensure message remains visible after parsing
      element.style.opacity = '1';
      element.style.display = 'flex';
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
    if (this.isSending) {
      console.warn('⚠️ Already sending a message, ignoring duplicate click');
      return;
    }

    const textarea = document.querySelector('.message-textarea');
    const content = textarea.value.trim();
    const sendBtn = document.querySelector('.send-button');

    if (!content && !window.pendingPhotoFile && !window.pendingFileObject) return;
    if (!this.getCurrentConversationId()) return;

    this.isSending = true;
    sendBtn.disabled = true;

    if (window.pendingPhotoFile || window.pendingFileObject) {
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
    const filePreview = document.getElementById('file-preview-container');
    const photoUpload = document.getElementById('photo-upload');
    const fileUpload = document.getElementById('file-upload');
    
    if (attachmentPreview) attachmentPreview.classList.add('hidden');
    if (photoPreview) photoPreview.classList.add('hidden');
    if (filePreview) filePreview.classList.add('hidden');
    if (photoUpload) photoUpload.value = '';
    if (fileUpload) fileUpload.value = '';
    
    window.pendingPhotoFile = null;
    window.pendingFileObject = null;
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
      .then((res) => {
        clearTimeout(timeoutId);
        console.log(`📩 Send response status: ${res.status}, headers:`, res.headers.get('content-type'));
        return res.json().then(data => ({ status: res.status, data }));
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

    if (pendingFile) {
      console.log('📄 Uploading file:', pendingFile.name);
      const formData = new FormData();
      formData.append('file', pendingFile.file);
      formData.append('type', 'file');
      uploads.push(this.uploadFileInternal(formData, 'file'));
    }

    if (uploads.length === 0) {
      console.log('✅ No files to upload, sending text only');
      this.isSending = false;
      sendBtn.disabled = false;
      if (!textContent.trim()) {
        this.showNotification('⚠️ Please enter a message or attach a file', 'warning');
        return;
      }
      this.sendTextMessageWithButton(textContent, sendBtn);
      return;
    }

    console.log(`⏳ Uploading ${uploads.length} file(s)...`);
    
    Promise.all(uploads)
      .then((results) => {
        console.log('✅ All files uploaded:', results);
        let finalContent = textContent || ''; // Start with text content
        
        // Add file references
        results.forEach((file) => {
          if (file && file.filename && file.url) {
            if (finalContent) finalContent += '\n'; // Add newline if there's existing content
            finalContent += `[${file.filename}](${file.url})`;
          }
        });
        
        // Ensure we have content to send
        if (!finalContent || !finalContent.trim()) {
          console.error('❌ No content to send after file upload');
          this.showNotification('❌ Error: No content or files to send', 'error');
          this.isSending = false;
          sendBtn.disabled = false;
          return;
        }
        
        console.log('📨 Sending message with attachments to database, content length:', finalContent.length);
        
        // Send the actual message with file references
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
    if (!convId) return Promise.reject(new Error('No conversation ID'));

    // Create abort controller with 120 second timeout for larger files
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => {
      console.error('⏱️ File upload timeout - aborting after 120 seconds');
      abortController.abort();
    }, 120000);

    console.log(`📤 Uploading ${fileType} to conversation ${convId}`);

    return fetch(`/messages/upload-file/${convId}`, {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': this.getCSRFToken(),
      },
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
        previewEl.textContent = messageData.content.substring(0, 50);
      }
    }
  }

  escapeHtml(text) {
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

  handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const validMimeTypes = [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  // .docx
      'text/plain',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  // .xlsx
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',  // .pptx
      'application/zip',
      'application/x-rar-compressed',
    ];
    
    // Check both MIME type and file extension as fallback
    const ext = file.name.split('.').pop().toLowerCase();
    const validExtensions = ['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar'];
    
    if (!validMimeTypes.includes(file.type) && !validExtensions.includes(ext)) {
      this.showNotification(`Invalid file format. Allowed: ${validExtensions.join(', ')}`, 'error');
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      this.showNotification('File too large (max 25MB)', 'error');
      return;
    }

    this.showFilePreview(file.name, file.size, ext, file);
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

  showFilePreview(filename, fileSize, ext, fileObject) {
    const previewContainer = document.getElementById('file-preview-container');
    const filenameEl = document.getElementById('file-preview-name');
    const filesizeEl = document.getElementById('file-preview-size');
    const fileIcon = document.getElementById('file-preview-icon');
    const attachmentPreview = document.getElementById('attachment-preview');

    if (!previewContainer) return;

    const icon = this.getFileIcon(ext);
    fileIcon.className = `fas ${icon}`;
    filenameEl.textContent = filename;
    filesizeEl.textContent = this.formatFileSize(fileSize);

    previewContainer.classList.remove('hidden');
    attachmentPreview.classList.remove('hidden');
    window.pendingFileObject = fileObject;
  }

  removePhotoPreview() {
    const previewContainer = document.getElementById('photo-preview-container');
    const attachmentPreview = document.getElementById('attachment-preview');
    const photoUpload = document.getElementById('photo-upload');

    if (previewContainer) previewContainer.classList.add('hidden');
    if (!document.getElementById('file-preview-container').classList.contains('hidden')) {
      attachmentPreview.classList.remove('hidden');
    } else {
      attachmentPreview.classList.add('hidden');
    }

    photoUpload.value = '';
    window.pendingPhotoFile = null;
  }

  removeFilePreview() {
    const previewContainer = document.getElementById('file-preview-container');
    const attachmentPreview = document.getElementById('attachment-preview');
    const fileUpload = document.getElementById('file-upload');

    if (previewContainer) previewContainer.classList.add('hidden');
    if (!document.getElementById('photo-preview-container').classList.contains('hidden')) {
      attachmentPreview.classList.remove('hidden');
    } else {
      attachmentPreview.classList.add('hidden');
    }

    fileUpload.value = '';
    window.pendingFileObject = null;
  }

  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  }

  getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
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
    const fileBtn = document.getElementById('file-btn');
    const photoUpload = document.getElementById('photo-upload');
    const fileUpload = document.getElementById('file-upload');
    const removePhotoPreviewBtn = document.getElementById('remove-photo-preview');
    const removeFilePreviewBtn = document.getElementById('remove-file-preview');
    const photoPreviewContainer = document.getElementById('photo-preview-container');
    const filePreviewContainer = document.getElementById('file-preview-container');

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
      photoBtn.addEventListener('click', () => photoUpload.click());
    }

    if (fileBtn) {
      fileBtn.addEventListener('click', () => fileUpload.click());
    }

    if (photoUpload) {
      photoUpload.addEventListener('change', (e) => this.handlePhotoUpload(e));
    }

    if (fileUpload) {
      fileUpload.addEventListener('change', (e) => this.handleFileUpload(e));
    }

    // Preview remove button handlers
    if (removePhotoPreviewBtn) {
      removePhotoPreviewBtn.addEventListener('click', () => this.removePhotoPreview());
    }

    if (removeFilePreviewBtn) {
      removeFilePreviewBtn.addEventListener('click', () => this.removeFilePreview());
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

    if (filePreviewContainer) {
      filePreviewContainer.addEventListener('click', (e) => {
        if (e.target.id !== 'remove-file-preview' && !e.target.closest('#remove-file-preview')) {
          const fileName = document.getElementById('file-preview-name')?.textContent || 'document.pdf';
          this.showNotification('ℹ️ Send the file to preview it in the chat', 'info');
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
  window.messagingApp = new MessagingApp();

  // Parse ALL initial messages (both with and without data-needs-parse attribute)
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
  }, 100);
});
