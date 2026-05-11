/**
 * STORE PAGE - VANILLA JAVASCRIPT
 * Modern, clean implementation with file upload and modal functionality
 */

// ================================
// DOM ELEMENTS
// ================================
const uploadArea = document.getElementById('uploadArea');
const logoInput = document.getElementById('logoInput');
const preview = document.getElementById('preview');
const previewImage = document.getElementById('previewImage');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const uploadBtn = document.getElementById('uploadBtn');
const logoUploadModal = document.getElementById('logoUploadModal');
const uploadProgress = document.getElementById('uploadProgress');
const progressFill = document.getElementById('progressFill');
const storeLogo = document.getElementById('store-logo');
const chooseImageBtn = document.getElementById('chooseImageBtn');
const notificationContainer = document.getElementById('notificationContainer');
const loaderOverlay = document.getElementById('loader-overlay');
const progressBar = document.getElementById('progressBar');

// ================================
// INITIALIZATION
// ================================
document.addEventListener('DOMContentLoaded', function() {
  initializeUploadArea();
  initializeModal();
  initializeChooseButton();
});

// ================================
// CHOOSE IMAGE BUTTON
// ================================
function initializeChooseButton() {
  if (chooseImageBtn && logoInput) {
    chooseImageBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      logoInput.click();
    });
  }
}

// ================================
// UPLOAD AREA FUNCTIONALITY
// ================================
function initializeUploadArea() {
  if (!uploadArea) return;

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
    if (files.length > 0) {
      logoInput.files = files;
      handleFileSelect(files[0]);
    }
  });

  // Handle file input change
  logoInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelect(e.target.files[0]);
    }
  });

  // Make entire upload area clickable
  uploadArea.addEventListener('click', (e) => {
    if (e.target === logoInput) {
      return;
    }
    logoInput.click();
  });
}

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function handleFileSelect(file) {
  // Validate file type
  const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
  if (!validTypes.includes(file.type)) {
    showNotification('Please select a JPG, PNG, or WebP image', 'error');
    logoInput.value = '';
    preview.classList.add('hidden');
    return;
  }

  // Validate file size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    showNotification('File is too large. Maximum size is 5MB', 'error');
    logoInput.value = '';
    preview.classList.add('hidden');
    return;
  }

  // Validate image dimensions
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = () => {
      if (img.width < 100 || img.height < 100) {
        showNotification('Image must be at least 100x100 pixels', 'error');
        logoInput.value = '';
        preview.classList.add('hidden');
        return;
      }

      // Show preview
      previewImage.src = e.target.result;
      fileName.textContent = file.name;
      fileSize.textContent = formatFileSize(file.size);
      preview.classList.remove('hidden');
      uploadArea.style.display = 'none';
    };
    img.onerror = () => {
      showNotification('Invalid image file', 'error');
      logoInput.value = '';
      preview.classList.add('hidden');
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// ================================
// MODAL FUNCTIONALITY
// ================================
function initializeModal() {
  if (!logoUploadModal) return;

  // Close modal when clicking outside
  logoUploadModal.addEventListener('click', (e) => {
    if (e.target === logoUploadModal) {
      closeLogoUploadModal();
    }
  });

  // Close modal with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !logoUploadModal.classList.contains('hidden')) {
      closeLogoUploadModal();
    }
  });
}

function openLogoUploadModal() {
  logoUploadModal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeLogoUploadModal() {
  logoUploadModal.classList.add('hidden');
  logoInput.value = '';
  preview.classList.add('hidden');
  uploadArea.style.display = 'block';
  uploadProgress.classList.add('hidden');
  progressFill.style.width = '0%';
  document.body.style.overflow = 'auto';
}

// ================================
// FILE UPLOAD
// ================================
function uploadLogo(event) {
  event.preventDefault();

  const file = logoInput.files[0];
  if (!file) {
    showNotification('Please select a file first', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('logo', file);

  uploadBtn.disabled = true;
  uploadProgress.classList.remove('hidden');
  uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Uploading...</span>';

  // Show global loader
  showLoader('Uploading your logo...');

  let simulatedProgress = 0;
  const simulationInterval = setInterval(() => {
    simulatedProgress += Math.random() * 30;
    if (simulatedProgress > 90) simulatedProgress = 90;
    progressFill.style.width = simulatedProgress + '%';
  }, 100);

  fetch(window.logoUploadUrl, {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
    .then(response => {
      // Check content type first
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        // If not JSON, read as text to show error
        return response.text().then(text => {
          console.error('Non-JSON response received:', text);
          throw new Error(`Server returned ${response.status}: Expected JSON but got ${contentType || 'unknown type'}`);
        });
      }
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} error!`);
      }
      return response.json();
    })
    .then(data => {
      clearInterval(simulationInterval);
      progressFill.style.width = '100%';

      if (data.success) {
        showNotification('Logo uploaded successfully!', 'success');

        // Update logo image with cache bust
        if (storeLogo) {
          const timestamp = new Date().getTime();
          if (storeLogo.tagName === 'DIV') {
            // Replace placeholder with image
            const img = document.createElement('img');
            img.id = 'store-logo';
            img.className = storeLogo.className;
            img.src = data.logo_url + '?' + timestamp;
            img.alt = 'Store Logo';
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'cover';
            storeLogo.parentNode.replaceChild(img, storeLogo);
          } else {
            storeLogo.src = data.logo_url + '?' + timestamp;
          }
        }

        // Close modal and hide loader
        setTimeout(() => {
          closeLogoUploadModal();
          hideLoader();
        }, 800);
      } else {
        showNotification('Upload failed: ' + (data.message || 'Unknown error'), 'error');
        hideLoader();
      }
    })
    .catch(error => {
      clearInterval(simulationInterval);
      console.error('Upload error:', error);
      console.error('Error details:', error.message);
      showNotification('Upload failed: ' + error.message, 'error');
      hideLoader();
    })
    .finally(() => {
      uploadBtn.disabled = false;
      uploadBtn.innerHTML = '<i class="fas fa-upload"></i> <span>Upload</span>';
      uploadProgress.classList.add('hidden');
      progressFill.style.width = '0%';
    });
}

// ================================
// NOTIFICATIONS
// ================================
function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  
  const bgColors = {
    success: 'bg-green-500',
    error: 'bg-red-500',
    warning: 'bg-yellow-500',
    info: 'bg-blue-500'
  };

  const icons = {
    success: 'fas fa-check-circle',
    error: 'fas fa-exclamation-circle',
    warning: 'fas fa-exclamation-triangle',
    info: 'fas fa-info-circle'
  };

  notification.className = `${bgColors[type] || bgColors.info} text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-3 animate-fade-in`;
  notification.innerHTML = `
    <i class="${icons[type] || icons.info}"></i>
    <span>${message}</span>
  `;

  if (notificationContainer) {
    notificationContainer.appendChild(notification);
  } else {
    document.body.appendChild(notification);
  }

  // Auto-remove after 4 seconds
  setTimeout(() => {
    notification.style.opacity = '0';
    notification.style.transform = 'translateX(400px)';
    notification.style.transition = 'all 0.3s ease';
    setTimeout(() => notification.remove(), 300);
  }, 4000);
}

// ================================
// LOADER MANAGEMENT
// ================================
function showLoader(message = 'Loading...') {
  if (loaderOverlay) {
    loaderOverlay.classList.remove('hidden');
    const messageEl = loaderOverlay.querySelector('span');
    if (messageEl) {
      messageEl.textContent = message;
    }
  }
}

function hideLoader() {
  if (loaderOverlay) {
    loaderOverlay.classList.add('hidden');
  }
}

// ================================
// EXPORT FOR GLOBAL ACCESS
// ================================
window.openLogoUploadModal = openLogoUploadModal;
window.closeLogoUploadModal = closeLogoUploadModal;
window.uploadLogo = uploadLogo;
window.showNotification = showNotification;
