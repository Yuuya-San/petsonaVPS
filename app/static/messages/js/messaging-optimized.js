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
  }

  // ==================== SOCKET.IO SETUP ====================

  connectSocket() {
    if (window.sharedSocket && window.sharedSocket.connected) {
      this.socket = window.sharedSocket;
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
      console.log('Socket connected');
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
      console.log('Socket disconnected:', reason);
    });

    this.socket.on('connect_error', (error) => {
      console.error('Socket connection error:', error);
    });
  }

  // ==================== MESSAGE HANDLING ====================

  handleNewMessage(messageData) {
    const currentUserId = parseInt(document.querySelector('[data-current-user-id]')?.dataset.currentUserId);
    const isOwnMessage = messageData.sender_id === currentUserId;
    
    if (!isOwnMessage) {
      this.addMessageToDOM(messageData, false);
      this.updateConversationPreview(messageData);
    }
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
    messageEl.setAttribute('data-needs-parse', 'true');

    const statusHTML = isOwn
      ? `<div class="message-status">
           <span class="status-icon status-delivered">
             <i class="fas fa-check text-gray-400"></i>
           </span>
         </div>`
      : '';

    messageEl.innerHTML = `
      <div class="message-content">
        <div class="message-text message-parser">${messageData.content}</div>
        <div class="message-time">${messageData.created_at_formatted_full || messageData.created_at_formatted}</div>
        ${statusHTML}
      </div>
    `;

    if (isOwn) {
      const menuBtn = document.createElement('button');
      menuBtn.className = 'message-menu-btn';
      menuBtn.innerHTML = '<i class="fas fa-ellipsis-v"></i>';
      menuBtn.onclick = () => this.showMessageMenu(messageData.id);
      messageEl.appendChild(menuBtn);
    }

    chatMessages.appendChild(messageEl);
    
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
                      <img src="${this.escapeHtml(url)}" alt="${this.escapeHtml(filename)}" class="media-image" onclick="openDownloadDialog('${this.escapeHtml(url)}', '${this.escapeHtml(filename)}', 'image')">
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
    }

    messageParser.dataset.parsed = 'true';
  }

  // ==================== MESSAGE ACTIONS - OPTIMIZED ====================

  sendMessage() {
    if (this.isSending) return;

    const textarea = document.querySelector('.message-textarea');
    const content = textarea.value.trim();
    const sendBtn = document.querySelector('.send-button');

    if (!content && !window.pendingPhotoFile && !window.pendingFileObject) return;
    if (!this.currentConversationId) return;

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
    if (!content || !this.currentConversationId) return;

    // OPTIMISTIC UPDATE: Add message to DOM immediately (showing as pending/sending)
    const tempMessageId = `temp-${Date.now()}`;
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    const messageEl = document.createElement('div');
    messageEl.className = 'message-bubble own animate-slide-in-up';
    messageEl.setAttribute('data-message-id', tempMessageId);

    messageEl.innerHTML = `
      <div class="message-content">
        <div class="message-text message-parser">${this.escapeHtml(content)}</div>
        <div class="message-time" style="display:flex; align-items:center; gap:6px; font-size:0.75rem;">
          <span>sending...</span>
          <div class="sending-spinner">
            <div class="spinner-dot"></div>
            <div class="spinner-dot"></div>
            <div class="spinner-dot"></div>
          </div>
        </div>
      </div>
      <div class="message-status">
        <span class="status-icon status-sending">
          <i class="fas fa-clock text-gray-400"></i>
        </span>
      </div>
    `;

    chatMessages.appendChild(messageEl);
    this.scrollToBottom();
    console.log('💭 Optimistic message added to DOM:', tempMessageId);

    // Create abort controller with 30 second timeout for message send
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 30000);

    // Send to server
    fetch(`/messages/send-message/${this.currentConversationId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCSRFToken(),
      },
      body: JSON.stringify({ content: content }),
      signal: abortController.signal,
    })
      .then((res) => res.json())
      .then((data) => {
        clearTimeout(timeoutId);
        
        const messageEl = document.querySelector(`[data-message-id="${tempMessageId}"]`);
        if (!messageEl) return;

        if (data.success) {
          console.log('✅ Message confirmed by server:', data.message.id);
          // Update message with server data
          messageEl.setAttribute('data-message-id', data.message.id);
          const timeEl = messageEl.querySelector('.message-time');
          const statusEl = messageEl.querySelector('.message-status');
          
          if (timeEl) {
            timeEl.innerHTML = `${data.message.created_at_formatted_full || data.message.created_at_formatted}`;
          }
          if (statusEl) {
            statusEl.innerHTML = '<span class="status-icon status-delivered"><i class="fas fa-check text-gray-400"></i></span>';
          }

          // Parse media if any
          const messageParser = messageEl.querySelector('.message-parser');
          if (messageParser && messageParser.innerHTML.includes('[')) {
            this.scheduleMediaParse(messageEl);
          }
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
              this.showNotification('Message send timed out - check your connection', 'warning');
            } else {
              timeEl.innerHTML = `<span class="text-red-500 text-xs">Network error - <span class="cursor-pointer hover:underline" onclick="messagingApp.retryMessage('${tempMessageId}')">retry</span></span>`;
              this.showNotification('Network error', 'warning');
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
      <div class="message-content">
        <div class="message-text">${this.escapeHtml(content)}</div>
        <div class="message-time" style="display:flex; align-items:center; gap:6px;">
          <span style="font-size: 0.75rem;">sending...</span>
          <div class="sending-spinner">
            <div class="spinner-dot"></div>
            <div class="spinner-dot"></div>
            <div class="spinner-dot"></div>
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
    this.clearPreview();

    const uploads = [];

    if (window.pendingPhotoFile) {
      console.log('📷 Uploading photo:', window.pendingPhotoFile.name);
      const formData = new FormData();
      formData.append('file', window.pendingPhotoFile);
      formData.append('type', 'photo');
      uploads.push(this.uploadFileInternal(formData));
    }

    if (window.pendingFileObject) {
      console.log('📄 Uploading file:', window.pendingFileObject.name);
      const formData = new FormData();
      formData.append('file', window.pendingFileObject);
      formData.append('type', 'file');
      uploads.push(this.uploadFileInternal(formData));
    }

    if (uploads.length === 0) {
      console.log('✅ No files to upload, sending text only');
      this.sendTextMessageWithButton(textContent, sendBtn);
      return;
    }

    console.log(`⏳ Uploading ${uploads.length} file(s)...`);

    Promise.all(uploads)
      .then((results) => {
        console.log('✅ All files uploaded');
        let finalContent = textContent;
        results.forEach((file) => {
          if (file.filename) {
            finalContent += `\n[${file.filename}](${file.url})`;
          }
        });
        console.log('📨 Sending message with attachments');
        this.sendTextMessageWithButton(finalContent, sendBtn);
      })
      .catch((err) => {
        console.error('❌ Upload error:', err);
        this.isSending = false;
        sendBtn.disabled = false;
        
        // Provide specific error messages
        if (err.message.includes('timed out')) {
          this.showNotification('File upload too slow - check your network connection', 'error');
        } else if (err.message.includes('Network')) {
          this.showNotification('Network error uploading file', 'error');
        } else {
          this.showNotification('Error uploading files: ' + err.message, 'error');
        }
      })
      .finally(() => {
        this.isSending = false;
        sendBtn.disabled = false;
      });
  }

  uploadFileInternal(formData) {
    const convId = document.querySelector('[data-conversation-id]')?.dataset.conversationId;
    if (!convId) return Promise.reject('No conversation ID');

    // Create abort controller with 60 second timeout
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 60000);

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
        return res.json();
      })
      .then((data) => {
        if (data.success) {
          return { filename: data.filename, url: data.url };
        }
        throw new Error(data.error);
      })
      .catch((err) => {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError') {
          throw new Error('File upload timed out after 1 minute');
        }
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
    if (!this.isTyping && this.socket && this.currentConversationId) {
      this.isTyping = true;
      this.socket.emit('user_typing', { conversation_id: this.currentConversationId });
    }

    clearTimeout(this.typingTimeout);
    this.typingTimeout = setTimeout(() => this.stopTyping(), 2000);
  }

  stopTyping() {
    if (this.isTyping && this.socket && this.currentConversationId) {
      this.isTyping = false;
      this.socket.emit('user_stopped_typing', { conversation_id: this.currentConversationId });
    }
    clearTimeout(this.typingTimeout);
  }

  showTypingIndicator(data) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages || data.user_id === this.getCurrentUserId()) return;

    const existing = document.querySelector('.typing-indicator');
    if (existing) return;

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
    if (typingEl) typingEl.remove();
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
      'text/plain',
      'application/zip',
    ];
    if (!validMimeTypes.includes(file.type)) {
      this.showNotification('Invalid file format', 'error');
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      this.showNotification('File too large (max 25MB)', 'error');
      return;
    }

    const ext = file.name.split('.').pop().toLowerCase();
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
  }

  loadInitialData() {
    const convId = document.querySelector('[data-conversation-id]')?.dataset.conversationId;
    if (convId) {
      this.currentConversationId = parseInt(convId);
    }
  }
}

// Global helper functions
function openDownloadDialog(url, filename, type) {
  const modal = document.createElement('div');
  modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
  modal.innerHTML = `
    <div class="bg-white rounded-lg p-6 max-w-sm w-11/12">
      <button onclick="this.closest('div').remove()" class="float-right text-gray-500 text-2xl">&times;</button>
      <div class="clear-both">
        ${
          type === 'image'
            ? `<img src="${filename.replace(/"/g, '&quot;')}" class="w-full rounded mb-4">`
            : `<div class="text-center py-8"><i class="fas fa-file text-4xl text-gray-400 mb-4"></i><p>${filename}</p></div>`
        }
        <a href="${url.replace(/"/g, '&quot;')}" download class="block text-center bg-purple-600 text-white py-2 rounded mb-2">Download</a>
        <button onclick="this.closest('div').remove()" class="w-full bg-gray-300 text-gray-700 py-2 rounded">Close</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  window.messagingApp = new MessagingApp();

  // Parse initial messages
  setTimeout(() => {
    document.querySelectorAll('.message-parser[data-needs-parse="true"]').forEach((el) => {
      messagingApp.parseMediaInElement(el.closest('.message-bubble'));
    });
  }, 100);
});
