/**
 * Socket.IO Manager for Real-Time Vote Updates
 * Handles WebSocket connections and vote count synchronization
 */

class SocketManager {
  constructor() {
    this.socket = null;
    this.connected = false;
    this.watchers = new Map(); // species_id -> callback function
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    // Disable debug logging for performance
    this.debugMode = false;
    this.init();
  }

  log(...args) {
    if (this.debugMode) console.log(...args);
  }

  /**
   * Initialize Socket.IO connection
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
        window.sharedSocket = io({
          reconnection: true,
          reconnectionDelay: 500,
          reconnectionDelayMax: 2000,
          reconnectionAttempts: this.maxReconnectAttempts,
          transports: ['websocket', 'polling'],
          upgrade: true,
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

    // Vote update from server
    this.socket.on('vote_update', (data) => {
      const { species_id, vote_count } = data;
      this.log(`📡 Vote update received for species ${species_id}: ${vote_count} votes`);
      
      // Call registered callback for this species
      if (this.watchers.has(species_id)) {
        const callback = this.watchers.get(species_id);
        callback(vote_count);
      }
    });

    // Watch confirmation
    this.socket.on('watch_confirmed', (data) => {
      this.log('✅ Watch confirmed:', data);
    });

    // Reconnection attempt
    this.socket.on('reconnect_attempt', () => {
      this.reconnectAttempts++;
      this.log(`⏳ Reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
    });

    // Reconnection successful
    this.socket.on('reconnect', () => {
      this.connected = true;
      this.reconnectAttempts = 0;
      console.log('🔄 Socket.IO reconnected');
    });
  }

  /**
   * Register a watcher for a specific species
   * @param {number} speciesId - The species ID to watch
   * @param {function} callback - Function to call when vote count changes
   */
  watchSpecies(speciesId, callback) {
    if (!this.socket || !this.connected) {
      console.warn(`⏳ Socket not ready yet. Retrying watcher setup...`);
      setTimeout(() => this.watchSpecies(speciesId, callback), 100);
      return;
    }

    // Store callback
    this.watchers.set(speciesId, callback);

    // Notify server
    this.socket.emit('watch_species', { species_id: speciesId });
    console.log(`👁️ Watching species ${speciesId}`);
  }

  /**
   * Unregister a watcher for a specific species
   * @param {number} speciesId - The species ID to unwatch
   */
  unwatchSpecies(speciesId) {
    if (!this.socket) return;

    this.watchers.delete(speciesId);
    this.socket.emit('unwatch_species', { species_id: speciesId });
    console.log(`👁️ Stopped watching species ${speciesId}`);
  }

  /**
   * Re-watch all species after reconnection
   */
  rewatchAllSpecies() {
    console.log(`🔄 Re-registering ${this.watchers.size} species watchers...`);
    for (const [speciesId, callback] of this.watchers.entries()) {
      this.socket.emit('watch_species', { species_id: speciesId });
    }
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
}

// Create global instance
const socketManager = new SocketManager();

// Also expose socket globally for backward compatibility with inline scripts
window.socket = socketManager.socket;
