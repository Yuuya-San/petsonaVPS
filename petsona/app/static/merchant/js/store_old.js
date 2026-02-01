/**
 * STORE PAGE - JAVASCRIPT
 * Handles modal interactions, file uploads, drag-drop, and animations
 */

// ================================
// DOM ELEMENTS
// ================================
const uploadArea = document.getElementById('uploadArea');
const logoInput = document.getElementById('logoInput');
const preview = document.getElementById('preview');
const previewImage = document.getElementById('previewImage');
const fileName = document.getElementById('fileName');
const uploadBtn = document.getElementById('uploadBtn');
const logoUploadModal = document.getElementById('logoUploadModal');
const uploadProgress = document.getElementById('uploadProgress');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const storeLogo = document.getElementById('store-logo');

// ================================
// INITIALIZATION
// ================================
document.addEventListener('DOMContentLoaded', function() {
  initializeUploadArea();
  initializeModal();
  animateOnLoad();
  initializeSocketIO();
});

// ================================
// UPLOAD AREA FUNCTIONALITY
// ================================
function initializeUploadArea() {
  // Prevent default drag behavior
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    uploadArea.addEventListener(eventName, preventDefaults, false);
    document.body.addEventListener(eventName, preventDefaults, false);
  });

  // Highlight drop area when item is dragged over it
  ['dragenter', 'dragover'].forEach(eventName => {
    uploadArea.addEventListener(eventName, () => {
      uploadArea.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    uploadArea.addEventListener(eventName, () => {
      uploadArea.classList.remove('drag-over');
    });
  });

  // Handle dropped files
  uploadArea.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    logoInput.files = files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  });

  // Handle file input change
  logoInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelect(e.target.files[0]);
    }
  });
}

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function handleFileSelect(file) {
  // Validate file type
  if (!['image/jpeg', 'image/png'].includes(file.type)) {
    showNotification('Please select a JPG or PNG file', 'error');
    logoInput.value = '';
    preview.style.display = 'none';
    return;
  }

  // Validate file size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    showNotification('File is too large. Maximum size is 5MB', 'error');
    logoInput.value = '';
    preview.style.display = 'none';
    return;
  }

  // Show preview
  const reader = new FileReader();
  reader.onload = (e) => {
    previewImage.src = e.target.result;
    fileName.textContent = file.name;
    preview.style.display = 'block';
  };
  reader.readAsDataURL(file);
}

// ================================
// MODAL FUNCTIONALITY
// ================================
function initializeModal() {
  // Close modal when clicking outside
  logoUploadModal.addEventListener('click', (e) => {
    if (e.target.id === 'logoUploadModal') {
      closeLogoUploadModal();
    }
  });
}

function openLogoUploadModal() {
  logoUploadModal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeLogoUploadModal() {
  logoUploadModal.style.display = 'none';
  logoInput.value = '';
  preview.style.display = 'none';
  uploadProgress.style.display = 'none';
  progressFill.style.width = '0%';
  document.body.style.overflow = 'auto';
}

// ================================
// FILE UPLOAD
// ================================
function uploadLogo() {
  const file = logoInput.files[0];
  if (!file) {
    showNotification('Please select a file first', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('logo', file);

  uploadBtn.disabled = true;
  uploadProgress.style.display = 'block';
  uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';

  fetch(window.logoUploadUrl, {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      progressFill.style.width = '100%';
      showNotification('Logo uploaded successfully!', 'success');

      // Update logo image with cache bust
      storeLogo.src = data.logo_url + '?' + new Date().getTime();

      // Close modal and reload
      setTimeout(() => {
        closeLogoUploadModal();
        // Optional: reload page to show changes
        // location.reload();
      }, 1500);
    } else {
      showNotification('Upload failed: ' + (data.message || 'Unknown error'), 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showNotification('Upload failed. Please try again.', 'error');
  })
  .finally(() => {
    uploadBtn.disabled = false;
    uploadBtn.innerHTML = '<i class="fas fa-upload"></i> Upload Logo';
    uploadProgress.style.display = 'none';
    progressFill.style.width = '0%';
  });
}

// ================================
// NOTIFICATIONS
// ================================
function showNotification(message, type = 'info') {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.textContent = message;

  // Add styles dynamically
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 1rem 1.5rem;
    background: ${getNotificationColor(type)};
    color: white;
    border-radius: 10px;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
    font-weight: 600;
    z-index: 10000;
    animation: slideIn 0.3s ease;
    max-width: 400px;
  `;

  document.body.appendChild(notification);

  // Auto remove after 4 seconds
  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => {
      notification.remove();
    }, 300);
  }, 4000);
}

function getNotificationColor(type) {
  const colors = {
    success: '#22c55e',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6'
  };
  return colors[type] || colors.info;
}

// ================================
// ANIMATIONS
// ================================
function animateOnLoad() {
  // Add animation styles
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from {
        transform: translateX(100%);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }

    @keyframes slideOut {
      from {
        transform: translateX(0);
        opacity: 1;
      }
      to {
        transform: translateX(100%);
        opacity: 0;
      }
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    .stat-block {
      animation: fadeInUp 0.6s ease forwards;
      opacity: 0;
    }

    @keyframes fadeInUp {
      from {
        opacity: 0;
        transform: translateY(20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
  `;
  document.head.appendChild(style);

  // Animate stat blocks
  const statBlocks = document.querySelectorAll('.stat-block');
  statBlocks.forEach((block, index) => {
    block.style.animationDelay = `${index * 0.1}s`;
  });

  // Animate status cards
  const statusCards = document.querySelectorAll('.status-card');
  statusCards.forEach((card, index) => {
    card.style.opacity = '0';
    card.style.animation = 'fadeInUp 0.6s ease forwards';
    card.style.animationDelay = `${0.3 + index * 0.1}s`;
  });

  // Animate table rows
  const tableRows = document.querySelectorAll('.bookings-table tbody tr');
  tableRows.forEach((row, index) => {
    row.style.opacity = '0';
    row.style.animation = 'fadeInUp 0.6s ease forwards';
    row.style.animationDelay = `${0.5 + index * 0.1}s`;
  });
}

// ================================
// SOCKET.IO - REAL-TIME STATUS
// ================================
function initializeSocketIO() {
  // Check if Socket.IO is available
  if (typeof io === 'undefined') {
    console.warn('Socket.IO not loaded');
    return;
  }

  const socket = io();

  socket.on('connect', () => {
    console.log('Connected to server');
  });

  // Listen for online status updates
  socket.on('merchant_online', (data) => {
    if (data.merchant_id === window.currentMerchantId) {
      updateOnlineStatus(true);
    }
  });

  socket.on('merchant_offline', (data) => {
    if (data.merchant_id === window.currentMerchantId) {
      updateOnlineStatus(false);
    }
  });

  socket.on('disconnect', () => {
    console.log('Disconnected from server');
    updateOnlineStatus(false);
  });
}

function updateOnlineStatus(isOnline) {
  const statusBadge = document.querySelector('.store-header .badge');
  if (!statusBadge) return;

  if (isOnline) {
    statusBadge.innerHTML = '<i class="fas fa-circle"></i> Online';
    statusBadge.style.background = 'rgba(34, 197, 94, 0.3)';
  } else {
    statusBadge.innerHTML = '<i class="fas fa-circle"></i> Offline';
    statusBadge.style.background = 'rgba(239, 68, 68, 0.3)';
  }
}

// ================================
// INTERACTIVE FEATURES
// ================================

// Make status cards clickable for filtering
document.querySelectorAll('.status-card').forEach(card => {
  card.addEventListener('click', function() {
    const status = this.querySelector('.status-label').textContent.toLowerCase();
    // Could filter table by status here
    console.log('Filter by:', status);
  });
});

// Make table rows clickable
document.querySelectorAll('.bookings-table tbody tr').forEach(row => {
  row.addEventListener('click', function() {
    const bookingId = this.querySelector('.booking-id').textContent;
    // Could navigate to booking details here
    console.log('View booking:', bookingId);
  });
  
  row.style.cursor = 'pointer';
});

// ================================
// EXPORT FOR GLOBAL ACCESS
// ================================
window.openLogoUploadModal = openLogoUploadModal;
window.closeLogoUploadModal = closeLogoUploadModal;
window.uploadLogo = uploadLogo;
window.showNotification = showNotification;
