/**
 * Socket.IO Manager for Real-Time Updates - Production-Ready
 * Optimized with eventlet, compression, request deduplication, and batching
 * Prevents unnecessary requests to reduce system load
 */

class SocketManager {
  constructor() {
    this.socket = null;
    this.connected = false;
    this.watchers = new Map(); // species_id -> callback function
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.debugMode = false;
    
    // Request deduplication to prevent unnecessary emissions
    this.recentEmits = new Map(); // event_key -> timestamp
    this.deduplicationTTL = 1000; // 1 second
    
    // Event batching for high-frequency events
    this.eventBatch = new Map(); // event_type -> [events]
    this.batchTimers = new Map(); // event_type -> timer_id
    this.batchSize = 10;
    this.batchFlushInterval = 100; // 100ms
    
    this.init();
  }

  log(...args) {
    if (this.debugMode) console.log('[SocketManager]', ...args);
  }

  /**
   * Initialize Socket.IO connection with production settings
   */
  init() {
    try {
      // Check if Socket.IO library is available
      if (typeof io === 'undefined') {
        console.warn('⚠️ Socket.IO client library not loaded');
        return;
      }

      // Reuse existing global socket connection if available
      if (window.sharedSocket && window.sharedSocket.connected) {
        this.socket = window.sharedSocket;
        this.connected = true;
      } else if (!window.sharedSocket) {
        // Create shared socket instance for all modules
        // Production settings: WebSocket only (no polling overhead)
        window.sharedSocket = io({
          // Connection settings
          reconnection: true,
          reconnectionDelay: 500,
          reconnectionDelayMax: 3000,
          reconnectionAttempts: this.maxReconnectAttempts,
          
          // Transport optimization - Allow both WebSocket and polling for compatibility
          // WebSocket preferred, polling as fallback
          transports: ['websocket', 'polling'],
          
          // Allow protocol upgrade from polling to websocket if needed
          upgrade: true,
          rememberUpgrade: true,
          
          // Connection pooling and resource management
          forceNew: false,
          multiplex: true,
          
          // Timeout settings
          connectTimeout: 10000,
          ackTimeout: 5000,
        });
        this.socket = window.sharedSocket;
      } else {
        this.socket = window.sharedSocket;
      }

      this.setupEventHandlers();
    } catch (error) {
      console.error('❌ Error initializing Socket.IO:', error);
    }
  }

  /**
   * Setup Socket.IO event handlers
   */
  setupEventHandlers() {
    if (!this.socket) return;

    // Connection established
    this.socket.on('connect', () => {
      this.connected = true;
      this.reconnectAttempts = 0;
      this.log('🔗 Socket.IO connected:', this.socket.id);
      
      // Re-register watchers after reconnection
      this.rewatchAllSpecies();
      
      // Notify listeners that socket is ready
      window.dispatchEvent(new CustomEvent('socket-ready', { detail: this.socket }));
    });

    // Connection lost
    this.socket.on('disconnect', () => {
      this.connected = false;
      this.log('❌ Socket.IO disconnected');
    });

    // Server sent error
    this.socket.on('error', (error) => {
      console.error('❌ Socket.IO error:', error);
    });

    // Connection response
    this.socket.on('connection_response', (data) => {
      this.log('✅ Connection response:', data);
    });

    // Vote update from server - optimized
    this.socket.on('vote_update', (data) => {
      const { species_id, vote_count } = data;
      this.log(`📡 Vote update for species ${species_id}: ${vote_count}`);
      
      // Call registered callback for this species
      if (this.watchers.has(species_id)) {
        const callback = this.watchers.get(species_id);
        callback(vote_count);
      }
    });

    // Breed vote update
    this.socket.on('breed_vote_update', (data) => {
      this.log(`📡 Breed vote update for breed ${data.breed_id}`);
      window.dispatchEvent(new CustomEvent('breed-vote-update', { detail: data }));
    });

    // Watch confirmation
    this.socket.on('watch_confirmed', (data) => {
      this.log('✅ Watch confirmed:', data.species_id);
    });

    // User status changes
    this.socket.on('user_status_changed', (data) => {
      this.log(`👤 User status changed: ${data.user_id}`);
      window.dispatchEvent(new CustomEvent('user-status-changed', { detail: data }));
    });

    // Message events
    this.socket.on('new_message', (data) => {
      this.log(`💬 New message in conversation ${data.conversation_id}`);
      window.dispatchEvent(new CustomEvent('socket-new-message', { detail: data }));
    });

    this.socket.on('user_typing', (data) => {
      window.dispatchEvent(new CustomEvent('user-typing', { detail: data }));
    });

    this.socket.on('user_stopped_typing', (data) => {
      window.dispatchEvent(new CustomEvent('user-stopped-typing', { detail: data }));
    });

    // Navbar updates
    this.socket.on('navbar_message_update', (data) => {
      this.log(`📬 Navbar message update for user`);
      window.dispatchEvent(new CustomEvent('navbar-message-update', { detail: data }));
    });

    this.socket.on('message_unread_count_update', (data) => {
      window.dispatchEvent(new CustomEvent('unread-count-update', { detail: data }));
    });

    // Reconnection attempt
    this.socket.on('reconnect_attempt', () => {
      this.reconnectAttempts++;
      this.log(`⏳ Reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
    });

    // Reconnection successful
    this.socket.on('reconnect', () => {
      this.connected = true;
      this.reconnectAttempts = 0;
      console.log('🔄 Socket.IO reconnected');
    });
  }

  /**
   * Check if event is duplicate and too recent
   */
  isDuplicate(eventKey) {
    const now = Date.now();
    const lastTime = this.recentEmits.get(eventKey);
    
    if (lastTime && (now - lastTime) < this.deduplicationTTL) {
      return true;
    }
    
    this.recentEmits.set(eventKey, now);
    
    // Clean old entries periodically
    if (this.recentEmits.size > 1000) {
      for (const [key, time] of this.recentEmits.entries()) {
        if (now - time > 5000) { // Remove entries older than 5 seconds
          this.recentEmits.delete(key);
        }
      }
    }
    
    return false;
  }

  /**
   * Batch and emit events to reduce frequency
   */
  batchEmit(eventType, data) {
    if (!this.eventBatch.has(eventType)) {
      this.eventBatch.set(eventType, []);
    }
    
    const batch = this.eventBatch.get(eventType);
    batch.push(data);
    
    // If batch is full, flush immediately
    if (batch.length >= this.batchSize) {
      this.flushBatch(eventType);
      return;
    }
    
    // Otherwise, schedule flush
    if (!this.batchTimers.has(eventType)) {
      const timerId = setTimeout(() => {
        this.flushBatch(eventType);
      }, this.batchFlushInterval);
      this.batchTimers.set(eventType, timerId);
    }
  }

  /**
   * Flush accumulated batch events
   */
  flushBatch(eventType) {
    const batch = this.eventBatch.get(eventType);
    if (!batch || batch.length === 0) return;
    
    // Emit batched events
    if (batch.length === 1) {
      this.emitEvent(eventType, batch[0]);
    } else {
      this.emitEvent(`${eventType}_batch`, batch);
    }
    
    // Clear batch
    this.eventBatch.set(eventType, []);
    
    // Clear timer
    const timerId = this.batchTimers.get(eventType);
    if (timerId) {
      clearTimeout(timerId);
      this.batchTimers.delete(eventType);
    }
  }

  /**
   * Emit event with deduplication check
   */
  emitEvent(eventType, data, skipDedup = false) {
    if (!this.socket) return;
    
    const eventKey = `${eventType}_${JSON.stringify(data).substring(0, 50)}`;
    
    if (!skipDedup && this.isDuplicate(eventKey)) {
      this.log(`⏭️ Skipped duplicate event: ${eventType}`);
      return;
    }
    
    try {
      this.socket.emit(eventType, data);
      this.log(`📤 Emitted ${eventType}`);
    } catch (error) {
      console.error(`Error emitting ${eventType}:`, error);
    }
  }

  /**
   * Register a watcher for a specific species - optimized
   * @param {number} speciesId - The species ID to watch
   * @param {function} callback - Function to call when vote count changes
   */
  watchSpecies(speciesId, callback) {
    if (!this.socket || !this.connected) {
      console.warn(`⏳ Socket not ready. Retrying...`);
      setTimeout(() => this.watchSpecies(speciesId, callback), 100);
      return;
    }

    // Check if already watching
    if (this.watchers.has(speciesId)) {
      this.log(`Already watching species ${speciesId}`);
      return;
    }

    // Store callback
    this.watchers.set(speciesId, callback);

    // Notify server with deduplication
    this.emitEvent('watch_species', { species_id: speciesId });
  }

  /**
   * Unregister a watcher for a specific species - optimized
   * @param {number} speciesId - The species ID to unwatch
   */
  unwatchSpecies(speciesId) {
    if (!this.socket) return;

    // Check if actually watching
    if (!this.watchers.has(speciesId)) {
      return;
    }

    this.watchers.delete(speciesId);
    this.emitEvent('unwatch_species', { species_id: speciesId });
  }

  /**
   * Re-watch all species after reconnection - optimized batching
   */
  rewatchAllSpecies() {
    if (this.watchers.size === 0) return;
    
    console.log(`🔄 Re-registering ${this.watchers.size} watchers...`);
    
    // Batch the watch requests
    let batchCount = 0;
    for (const [speciesId] of this.watchers.entries()) {
      if (batchCount % 10 === 0) {
        // Small delay between batches to prevent overwhelming server
        setTimeout(() => {
          this.socket.emit('watch_species', { species_id: speciesId });
        }, batchCount * 10);
      } else {
        this.socket.emit('watch_species', { species_id: speciesId });
      }
      batchCount++;
    }
  }

  /**
   * Emit typing indicator with batching
   */
  emitTyping(conversationId) {
    if (!this.socket || !this.connected) return;
    
    const eventKey = `typing_${conversationId}`;
    if (this.isDuplicate(eventKey)) {
      return; // Skip if emitted recently
    }
    
    this.emitEvent('typing', { conversation_id: conversationId });
  }

  /**
   * Emit stop typing indicator
   */
  emitStopTyping(conversationId) {
    if (!this.socket || !this.connected) return;
    
    const eventKey = `stop_typing_${conversationId}`;
    if (this.isDuplicate(eventKey)) {
      return;
    }
    
    this.emitEvent('stop_typing', { conversation_id: conversationId });
  }

  /**
   * Check if socket is connected
   */
  isConnected() {
    return this.connected && this.socket && this.socket.connected;
  }

  /**
   * Manually disconnect
   */
  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.connected = false;
      console.log('🔌 Socket.IO disconnected');
    }
  }

  /**
   * Manually reconnect
   */
  reconnect() {
    if (this.socket) {
      this.socket.connect();
      console.log('🔄 Socket.IO reconnecting...');
    }
  }

  /**
   * Get connection statistics
   */
  getStats() {
    return {
      connected: this.connected,
      watchers: this.watchers.size,
      reconnectAttempts: this.reconnectAttempts,
      pendingBatches: this.eventBatch.size,
      recentEmits: this.recentEmits.size
    };
  }
}

// Create global instance
const socketManager = new SocketManager();

// Also expose socket globally for backward compatibility with inline scripts
window.socket = socketManager.socket;

// Export stats method for monitoring
window.getSocketStats = () => socketManager.getStats();
