// ===============================
// SETTINGS MODAL FUNCTIONALITY
// ===============================

document.addEventListener('DOMContentLoaded', function() {

  // ========== PASSWORD & SECURITY MODAL ==========
  const passwordForm = document.querySelector('#settingsAccountModal .settings-form');
  const newPasswordInput = document.getElementById('newPassword');
  const confirmPasswordInput = document.getElementById('confirmPassword');
  
  // Real-time password strength checking
  if (newPasswordInput) {
    newPasswordInput.addEventListener('input', function() {
      updatePasswordStrength(this.value);
    });
  }
  
  // Real-time password match checking
  if (confirmPasswordInput) {
    confirmPasswordInput.addEventListener('input', function() {
      checkPasswordMatch();
    });
  }
  
  if (passwordForm) {
    passwordForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const currentPassword = document.getElementById('currentPassword').value;
      const newPassword = document.getElementById('newPassword').value;
      const confirmPassword = document.getElementById('confirmPassword').value;
      
      // Validation
      if (!currentPassword) {
        showAlert('Please enter your current password', 'warning');
        return;
      }
      
      if (!newPassword || newPassword.length < 8) {
        showAlert('New password must be at least 8 characters', 'warning');
        return;
      }
      
      if (newPassword !== confirmPassword) {
        showAlert('Passwords do not match', 'error');
        return;
      }
      
      // Check password strength
      const passwordStrength = checkPasswordStrength(newPassword);
      if (passwordStrength < 3) {
        showAlert('Password must include uppercase, lowercase, numbers, and special characters', 'warning');
        return;
      }
      
      // Submit password change
      submitPasswordChange(currentPassword, newPassword);
    });
  }

  // ========== TWO-FACTOR AUTHENTICATION ==========
  const setupTwoFAButtons = document.querySelectorAll('[data-toggle="modal"][data-target="#settingsTwoFactorModal"]');
  
  // QR Code button handler
  const qrCodeBtn = document.querySelector('#settingsTwoFactorModal .btn-glass-primary');
  if (qrCodeBtn) {
    qrCodeBtn.addEventListener('click', function(e) {
      e.preventDefault();
      showQRCodeModal();
    });
  }

  // Reset Authenticator button
  const resetAuthBtn = document.querySelectorAll('#settingsTwoFactorModal .btn-glass-secondary')[0];
  if (resetAuthBtn) {
    resetAuthBtn.addEventListener('click', function(e) {
      e.preventDefault();
      if (confirm('Are you sure you want to reset your authenticator? Make sure you have saved your backup codes.')) {
        resetAuthenticator();
      }
    });
  }

  // Copy Backup Codes button
  const copyCodesBtn = document.querySelectorAll('#settingsTwoFactorModal .btn-glass-secondary')[1];
  if (copyCodesBtn) {
    copyCodesBtn.addEventListener('click', function(e) {
      e.preventDefault();
      copyBackupCodes();
    });
  }

  // ========== EMAIL PREFERENCES ==========
  const emailSaveBtn = document.querySelector('#settingsEmailModal .btn-glass-primary');
  if (emailSaveBtn) {
    emailSaveBtn.addEventListener('click', function(e) {
      e.preventDefault();
      saveEmailPreferences();
    });
  }

  // ========== PRIVACY SETTINGS ==========
  const privacySaveBtn = document.querySelector('#settingsPrivacyModal .btn-glass-primary');
  if (privacySaveBtn) {
    privacySaveBtn.addEventListener('click', function(e) {
      e.preventDefault();
      savePrivacySettings();
    });
  }

  // Manage Blocked Users
  const manageBlockedBtn = document.querySelector('#settingsPrivacyModal .btn-glass-secondary');
  if (manageBlockedBtn) {
    manageBlockedBtn.addEventListener('click', function(e) {
      e.preventDefault();
      // Implement blocked users management
      showAlert('Opening blocked users management...', 'info');
    });
  }

  // ========== NOTIFICATIONS ==========
  const notifSaveBtn = document.querySelector('#settingsNotificationsModal .btn-glass-primary');
  if (notifSaveBtn) {
    notifSaveBtn.addEventListener('click', function(e) {
      e.preventDefault();
      saveNotificationSettings();
    });
  }

  // ========== APPEARANCE ==========
  const appearanceSaveBtn = document.querySelector('#settingsAppearanceModal .btn-glass-primary');
  if (appearanceSaveBtn) {
    appearanceSaveBtn.addEventListener('click', function(e) {
      e.preventDefault();
      saveAppearanceSettings();
    });
  }

  // ========== DATA & PRIVACY ==========
  const downloadDataBtn = document.querySelector('#settingsDataModal .btn-glass-primary');
  if (downloadDataBtn) {
    downloadDataBtn.addEventListener('click', function(e) {
      e.preventDefault();
      downloadUserData();
    });
  }

  const dataSaveBtn = document.querySelectorAll('#settingsDataModal .btn-glass-primary')[1];
  if (dataSaveBtn) {
    dataSaveBtn.addEventListener('click', function(e) {
      e.preventDefault();
      saveDataPrivacySettings();
    });
  }

  // ========== LANGUAGE & REGION ==========
  const languageSaveBtn = document.querySelector('#settingsLanguageModal .btn-glass-primary');
  if (languageSaveBtn) {
    languageSaveBtn.addEventListener('click', function(e) {
      e.preventDefault();
      saveLanguageSettings();
    });
  }

  // Disconnect Apps
  const disconnectBtns = document.querySelectorAll('#settingsDataModal .btn-glass-danger');
  disconnectBtns.forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      const appName = this.closest('.app-access-item').querySelector('strong').textContent;
      if (confirm(`Are you sure you want to disconnect ${appName}?`)) {
        disconnectApp(appName);
      }
    });
  });

  // Delete Account
  const deleteAccountBtn = document.querySelector('#settingsDataModal .danger-zone .btn-glass-danger');
  if (deleteAccountBtn) {
    deleteAccountBtn.addEventListener('click', function(e) {
      e.preventDefault();
      deleteAccount();
    });
  }
});

// ===============================
// UTILITY FUNCTIONS
// ===============================

/**
 * Update password strength indicator in real-time
 */
function updatePasswordStrength(password) {
  const strength = checkPasswordStrength(password);
  const progress = document.getElementById('strengthProgress');
  const strengthText = document.getElementById('strengthText');
  
  if (!progress || !strengthText) return;
  
  const strengthLevels = {
    0: { width: '0%', text: 'Weak', color: '#ef4444' },
    1: { width: '25%', text: 'Fair', color: '#f97316' },
    2: { width: '50%', text: 'Good', color: '#eab308' },
    3: { width: '75%', text: 'Strong', color: '#84cc16' },
    4: { width: '100%', text: 'Very Strong', color: '#22c55e' }
  };
  
  const level = strengthLevels[strength] || strengthLevels[0];
  progress.style.width = level.width;
  strengthText.textContent = `Password strength: ${level.text}`;
  strengthText.style.color = level.color;
}

/**
 * Check if passwords match in real-time
 */
function checkPasswordMatch() {
  const newPassword = document.getElementById('newPassword').value;
  const confirmPassword = document.getElementById('confirmPassword').value;
  const indicator = document.getElementById('matchIndicator');
  
  if (!indicator) return;
  
  if (!confirmPassword) {
    indicator.classList.remove('show');
    return;
  }
  
  indicator.classList.add('show');
  
  if (newPassword === confirmPassword && newPassword.length > 0) {
    indicator.classList.remove('nomatch');
    indicator.classList.add('match');
    indicator.innerHTML = '<i class="fas fa-check-circle"></i>Passwords match';
  } else {
    indicator.classList.remove('match');
    indicator.classList.add('nomatch');
    indicator.innerHTML = '<i class="fas fa-times-circle"></i>Passwords do not match';
  }
}

/**
 * Show alert notification
 */
function showAlert(message, type = 'info') {
  const alertClass = {
    'info': 'alert-info',
    'warning': 'alert-warning',
    'error': 'alert-danger',
    'success': 'alert-success'
  }[type] || 'alert-info';
  
  const alertHTML = `
    <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
      <i class="fas fa-${type === 'error' ? 'exclamation-circle' : type === 'success' ? 'check-circle' : 'info-circle'} mr-2"></i>
      ${message}
      <button type="button" class="close" data-dismiss="alert" aria-label="Close">
        <span aria-hidden="true">&times;</span>
      </button>
    </div>
  `;
  
  const container = document.querySelector('.content-wrapper') || document.body;
  const alertDiv = document.createElement('div');
  alertDiv.innerHTML = alertHTML;
  container.insertBefore(alertDiv.firstElementChild, container.firstChild);
  
  setTimeout(() => {
    const alert = container.querySelector('.alert');
    if (alert) alert.remove();
  }, 5000);
}

// ===============================
// PASSWORD & SECURITY
// ===============================

function submitPasswordChange(currentPassword, newPassword) {
  // Create FormData
  const formData = new FormData();
  formData.append('current_password', currentPassword);
  formData.append('new_password', newPassword);
  
  fetch('/api/change-password', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Password changed successfully!', 'success');
      document.querySelector('#settingsAccountModal .settings-form').reset();
      setTimeout(() => {
        $('#settingsAccountModal').modal('hide');
      }, 1000);
    } else {
      showAlert(data.message || 'Failed to change password', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

// ===============================
// TWO-FACTOR AUTHENTICATION
// ===============================

function showQRCodeModal() {
  showAlert('QR Code generation is being set up...', 'info');
  // This would typically fetch a QR code from your backend
}

function resetAuthenticator() {
  const formData = new FormData();
  formData.append('action', 'reset_authenticator');
  
  fetch('/api/2fa-settings', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Authenticator reset successfully!', 'success');
    } else {
      showAlert(data.message || 'Failed to reset authenticator', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

function copyBackupCodes() {
  const codesText = Array.from(document.querySelectorAll('.backup-code'))
    .map(code => code.textContent)
    .join('\n');
  
  navigator.clipboard.writeText(codesText).then(() => {
    showAlert('Backup codes copied to clipboard!', 'success');
  }).catch(() => {
    showAlert('Failed to copy codes', 'error');
  });
}

// ===============================
// EMAIL PREFERENCES
// ===============================

function saveEmailPreferences() {
  const preferences = {
    marketing: document.getElementById('emailMarketing').checked,
    security: document.getElementById('emailSecurity').checked,
    matches: document.getElementById('emailMatches').checked,
    messages: document.getElementById('emailMessages').checked,
    account: document.getElementById('emailAccount').checked,
    frequency: document.querySelector('#settingsEmailModal select').value
  };
  
  const formData = new FormData();
  formData.append('preferences', JSON.stringify(preferences));
  
  fetch('/api/email-preferences', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Email preferences saved!', 'success');
      setTimeout(() => {
        $('#settingsEmailModal').modal('hide');
      }, 1000);
    } else {
      showAlert(data.message || 'Failed to save preferences', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

// ===============================
// PRIVACY SETTINGS
// ===============================

function savePrivacySettings() {
  const privacy = {
    profile_visibility: document.querySelector('input[name="profileVisibility"]:checked').value,
    show_pet_details: document.getElementById('showPetDetails').checked,
    show_pet_photos: document.getElementById('showPetPhotos').checked,
    search_indexing: document.getElementById('searchIndexing').checked,
    show_in_directory: document.getElementById('showInDirectory').checked
  };
  
  const formData = new FormData();
  formData.append('privacy', JSON.stringify(privacy));
  
  fetch('/api/privacy-settings', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Privacy settings saved!', 'success');
      setTimeout(() => {
        $('#settingsPrivacyModal').modal('hide');
      }, 1000);
    } else {
      showAlert(data.message || 'Failed to save settings', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

// ===============================
// NOTIFICATION SETTINGS
// ===============================

function saveNotificationSettings() {
  const notifications = {
    push_matches: document.getElementById('pushMatches').checked,
    push_messages: document.getElementById('pushMessages').checked,
    push_activity: document.getElementById('pushActivity').checked,
    browser_notifications: document.getElementById('browserNotif').checked,
    notification_sound: document.getElementById('notifSound').checked,
    vibration: document.getElementById('vibration').checked,
    quiet_hours_enabled: document.getElementById('quietHours').checked,
    quiet_start: document.querySelector('#settingsNotificationsModal input[type="time"]').value,
    quiet_end: document.querySelectorAll('#settingsNotificationsModal input[type="time"]')[1].value
  };
  
  const formData = new FormData();
  formData.append('notifications', JSON.stringify(notifications));
  
  fetch('/api/notification-settings', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Notification settings saved!', 'success');
      setTimeout(() => {
        $('#settingsNotificationsModal').modal('hide');
      }, 1000);
    } else {
      showAlert(data.message || 'Failed to save settings', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

// ===============================
// APPEARANCE SETTINGS
// ===============================

function saveAppearanceSettings() {
  const appearance = {
    theme: document.querySelector('input[name="theme"]:checked').value,
    font_size: document.querySelector('#settingsAppearanceModal select').value,
    animations: document.getElementById('enableAnimations').checked
  };
  
  const formData = new FormData();
  formData.append('appearance', JSON.stringify(appearance));
  
  fetch('/api/appearance-settings', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Appearance settings saved! Refreshing page...', 'success');
      setTimeout(() => {
        location.reload();
      }, 1500);
    } else {
      showAlert(data.message || 'Failed to save settings', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

// ===============================
// DATA & PRIVACY
// ===============================

function downloadUserData() {
  showAlert('Starting download of your data...', 'info');
  
  fetch('/api/download-user-data', {
    method: 'GET'
  })
  .then(response => response.blob())
  .then(blob => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `petsona-data-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    showAlert('Data downloaded successfully!', 'success');
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('Failed to download data', 'error');
  });
}

function saveDataPrivacySettings() {
  const dataPrivacy = {
    analytics_consent: document.getElementById('analyticsConsent').checked,
    marketing_consent: document.getElementById('marketingConsent').checked
  };
  
  const formData = new FormData();
  formData.append('data_privacy', JSON.stringify(dataPrivacy));
  
  fetch('/api/data-privacy-settings', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Data & Privacy settings saved!', 'success');
      setTimeout(() => {
        $('#settingsDataModal').modal('hide');
      }, 1000);
    } else {
      showAlert(data.message || 'Failed to save settings', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

function disconnectApp(appName) {
  const formData = new FormData();
  formData.append('app_name', appName);
  
  fetch('/api/disconnect-app', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert(`${appName} disconnected successfully!`, 'success');
      location.reload();
    } else {
      showAlert(data.message || 'Failed to disconnect app', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

function deleteAccount() {
  const confirmed = confirm('Are you sure you want to delete your account? This action cannot be undone!');
  if (!confirmed) return;
  
  const finalConfirm = confirm('This will permanently delete your account and all associated data. Type "DELETE" if you\'re sure.');
  if (!finalConfirm) return;
  
  const formData = new FormData();
  formData.append('action', 'delete_account');
  
  fetch('/api/delete-account', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Account deletion initiated. Redirecting...', 'success');
      setTimeout(() => {
        window.location.href = '/';
      }, 2000);
    } else {
      showAlert(data.message || 'Failed to delete account', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}

// ===============================
// LANGUAGE & REGION
// ===============================

function saveLanguageSettings() {
  const language = {
    display_language: document.querySelectorAll('#settingsLanguageModal select')[0].value,
    country: document.querySelectorAll('#settingsLanguageModal select')[1].value,
    timezone: document.querySelectorAll('#settingsLanguageModal select')[2].value,
    date_format: document.querySelectorAll('#settingsLanguageModal select')[3].value,
    time_format: document.querySelectorAll('#settingsLanguageModal select')[4].value
  };
  
  const formData = new FormData();
  formData.append('language', JSON.stringify(language));
  
  fetch('/api/language-settings', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Language settings saved! Refreshing page...', 'success');
      setTimeout(() => {
        location.reload();
      }, 1500);
    } else {
      showAlert(data.message || 'Failed to save settings', 'error');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showAlert('An error occurred', 'error');
  });
}
