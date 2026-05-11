/**
 * Navbar Socket Manager - Real-time notification updates
 * Handles live notification badges and dropdown updates
 */

// === INJECT AGGRESSIVE CSS TO FORCE NEW DESIGN ===
function injectNotificationCSS() {
    const style = document.createElement('style');
    style.textContent = `
        /* FORCE NEW NOTIFICATION DESIGN AT RUNTIME */
        .notifications-dropdown .notification-item {
            display: flex !important;
            align-items: flex-start !important;
            gap: 12px !important;
            padding: 12px 15px !important;
            background: transparent !important;
            border: none !important;
            border-left: 3px solid transparent !important;
            color: inherit !important;
            text-decoration: none !important;
            transition: all 0.2s ease !important;
        }
        
        .notifications-dropdown .notification-item > div {
            display: flex !important;
            align-items: flex-start !important;
            gap: 12px !important;
            width: 100% !important;
        }
        
        .notifications-dropdown .notification-item p,
        .notifications-dropdown .notification-item span {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        
        .notifications-dropdown .notification-item:hover {
            background-color: #f8f9fa !important;
        }
        
        /* UNREAD NOTIFICATION STYLES */
        .notifications-dropdown .notification-item.unread {
            background-color: #f0f3ff !important;
            border-left: 3px solid #667eea !important;
            position: relative !important;
        }
        
        .notifications-dropdown .notification-item.unread::before {
            content: '' !important;
            position: absolute !important;
            top: 50% !important;
            right: 15px !important;
            transform: translateY(-50%) !important;
            width: 8px !important;
            height: 8px !important;
            background-color: #667eea !important;
            border-radius: 50% !important;
            box-shadow: 0 0 0 2px #f0f3ff !important;
        }
        
        .notifications-dropdown .notification-item.unread:hover {
            background-color: #e8ecff !important;
            box-shadow: inset 0 0 10px rgba(102, 126, 234, 0.1) !important;
        }
        
        .notifications-dropdown .notification-item i {
            display: inline !important;
            visibility: visible !important;
        }
    `;
    document.head.appendChild(style);
    console.log('✅ Notification CSS injected with unread indicators');
}

// Initialize Socket.IO connection for notifications (wait for Socket.IO to load)
// Use window namespace to avoid double-declaration errors if script loads twice
if (typeof notificationSocket === 'undefined') {
    var notificationSocket = null;  // Use var for function-scope level declaration
    var isSocketConnected = false;
    var allNotifications = []; // Store all notifications for modal navigation
    var currentNotificationIndex = -1; // Track current notification being viewed in modal
}

// ===== FORMAT DATE TIME TO 12-HOUR FORMAT WITH AM/PM =====
function format12HourTime(dateString) {
    try {
        const date = new Date(dateString);
        const options = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        };
        return date.toLocaleString('en-US', options);
    } catch (e) {
        return dateString;
    }
}

// Function to initialize Socket.IO when ready
function initializeNotificationSocket() {
    // Check if io is available (Socket.IO loaded)
    if (typeof io === 'undefined') {
        console.warn('⏳ Socket.IO not loaded yet, retrying in 500ms...');
        setTimeout(initializeNotificationSocket, 500);
        return;
    }

    console.log('📡 Socket.IO available, initializing notification socket...');

    notificationSocket = io({
        transports: ['websocket'],
        upgrade: false,
        reconnection: true,
        reconnection_delay: 1000,
        reconnection_delay_max: 5000,
        reconnection_attempts: 999
    });

    // === SOCKET CONNECTION EVENTS ===
    notificationSocket.on('connect', function() {
        console.log('✅ Notification Socket Connected');
        isSocketConnected = true;
        
        // Request initial notification count
        notificationSocket.emit('get_unread_count');
        notificationSocket.emit('get_notifications');
    });

    notificationSocket.on('disconnect', function() {
        console.log('❌ Notification Socket Disconnected');
        isSocketConnected = false;
    });

    notificationSocket.on('error', function(error) {
        console.error('🔥 Notification Socket Error:', error);
    });

    // === RECEIVED NOTIFICATION EVENTS ===
    notificationSocket.on('new_notification_received', function(data) {
        console.log('📬 New Notification:', data);
        handleNewNotification(data);
    });

    notificationSocket.on('unread_count', function(data) {
        console.log('🔔 Unread Count:', data.count);
        updateNotificationBadge(data.count);
    });

    notificationSocket.on('unread_count_update', function(data) {
        console.log('🔄 Unread Count Updated:', data.unread_count);
        updateNotificationBadge(data.unread_count);
    });

    notificationSocket.on('notifications_list', function(data) {
        console.log('📋 Notifications List:', data.notifications.length);
        displayNotifications(data.notifications, data.unread_count);
    });

    notificationSocket.on('notification_marked_read', function(data) {
        console.log('✓ Notification Marked Read - New Unread:', data.unread_count);
        updateNotificationBadge(data.unread_count);
    });

    notificationSocket.on('all_notifications_marked_read', function(data) {
        console.log('✓ All Notifications Marked Read');
        updateNotificationBadge(0);
    });

    notificationSocket.on('notification_detail', function(data) {
        console.log('📦 Received notification detail:', data);
        if (data.notification) {
            displayNotificationModal(data.notification);
        }
    });
}

// === NOTIFICATION BADGE UPDATE ===
function updateNotificationBadge(count) {
    const badge = document.getElementById('notification-badge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    }
}

// === EVENT DELEGATION HANDLER FOR NOTIFICATION ITEMS ===
function handleNotificationItemClick(e) {
    // Find the notification item that was clicked (might be a child element)
    const notifElement = e.target.closest('[data-notification-id]');
    
    if (!notifElement) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const notificationId = notifElement.getAttribute('data-notification-id');
    
    // Find the notification object in allNotifications array
    const notif = allNotifications.find(n => n.id == notificationId);
    
    if (notif) {
        // Find index of this notification
        currentNotificationIndex = allNotifications.findIndex(n => n.id == notificationId);
        displayNotificationModal(notif);
    }
}

// === HANDLE NOTIFICATION ITEM HOVER ===
document.addEventListener('mouseenter', function(e) {
    if (!e.target.closest) return;
    const notifElement = e.target.closest('[data-notification-id]');
    if (notifElement && notifElement.classList.contains('notification-item')) {
        notifElement.style.background = '#f8f9fa !important';
    }
}, true);

document.addEventListener('mouseleave', function(e) {
    if (!e.target.closest) return;
    const notifElement = e.target.closest('[data-notification-id]');
    if (notifElement && notifElement.classList.contains('notification-item')) {
        const notif = allNotifications.find(n => n.id == notifElement.getAttribute('data-notification-id'));
        notifElement.style.background = (notif && !notif.is_read) ? '#f0f3ff !important' : 'transparent !important';
    }
}, true);

// === HANDLE NEW NOTIFICATION ===
function handleNewNotification(notification) {
    // Update badge
    const badge = document.getElementById('notification-badge');
    if (badge) {
        const currentCount = parseInt(badge.textContent) || 0;
        const newCount = currentCount + 1;
        updateNotificationBadge(newCount);
    }
    
    // Refresh notifications list
    if (notificationSocket) {
        notificationSocket.emit('get_notifications');
    }
    
    // Show toast notification (optional)
    showToastNotification(notification);
}

// === DISPLAY NOTIFICATIONS DROPDOWN ===
function displayNotifications(notifications, unreadCount) {
    const container = document.querySelector('.notifications-scroll-container');
    if (!container) return;
    
    // Store all notifications globally for modal navigation
    allNotifications = notifications;
    
    container.innerHTML = '';
    
    if (notifications.length === 0) {
        container.parentElement.innerHTML = `
            <div class="text-center text-muted py-4" style="font-size: 0.9rem;">
                <i class="fas fa-bell mb-2" style="display: block; font-size: 1.5rem; opacity: 0.5;"></i>
                No notifications yet
            </div>
        `;
        return;
    }
    
    notifications.forEach(notif => {
        // Removed sender avatar display
        
        const notificationHTML = `
            <div data-notification-id="${notif.id}" class="dropdown-item notification-item ${notif.is_read ? '' : 'unread'}" style="display: flex !important; align-items: flex-start !important; cursor: pointer !important; transition: all 0.2s !important; padding: 12px 15px !important; border: none !important; background: ${notif.is_read ? 'transparent' : '#f0f3ff'} !important; color: inherit !important; text-decoration: none !important; width: 100% !important; border-left: 3px solid ${notif.is_read ? 'transparent' : '#667eea'} !important;">
                <div style="width: 100% !important; display: flex !important; align-items: flex-start !important; gap: 12px !important;">
                    <!-- Notification Content -->
                    <div style="flex: 1 !important; min-width: 0 !important;">
                        <!-- Title -->
                        <p class="mb-1" style="font-size: 0.95rem !important; font-weight: bold !important; color: #212529 !important; margin: 0 !important; padding: 0 !important;">${notif.title}</p>
                        
                        <!-- Message Preview -->
                        <p class="mb-0" style="text-overflow: ellipsis !important; overflow: hidden !important; white-space: nowrap !important; font-size: 0.85rem !important; color: #6c757d !important; margin: 4px 0 0 0 !important; padding: 0 !important;">
                            ${notif.message}
                        </p>
                        
                        <!-- Timestamp + Read Status -->
                        <div style="display: flex !important; align-items: center !important; gap: 8px !important; margin-top: 4px !important;">
                            <span style="display: block !important; font-size: 0.75rem !important; color: #adb5bd !important;">
                                ${notif.time_short || notif.time || 'Recently'}
                            </span>
                            ${notif.is_read ? '' : '<span style="display: inline-block !important; width: 6px !important; height: 6px !important; background: #667eea !important; border-radius: 50% !important; flex-shrink: 0 !important;"></span>'}
                        </div>
                    </div>
                    
                    <!-- Chevron -->
                    <i class="fas fa-chevron-right" style="color: ${notif.is_read ? '#ccc' : '#667eea'} !important; font-size: 0.8rem !important; flex-shrink: 0 !important; margin-top: 2px !important;" ></i>
                </div>
            </div>
            <div class="dropdown-divider"></div>
        `;
        container.innerHTML += notificationHTML;
    });
    
    // Use event delegation - attach single listener to container for ALL notification items
    // This ensures even dynamically updated items get proper event handling
    container.removeEventListener('click', handleNotificationItemClick);
    container.addEventListener('click', handleNotificationItemClick);
    
    // Update badge
    updateNotificationBadge(unreadCount);
}

// === TOAST NOTIFICATION (Browser Notification) ===
function showToastNotification(notification) {
    if (!('Notification' in window)) return;
    
    if (Notification.permission === 'granted') {
        new Notification(notification.title, {
            icon: '/static/images/logo/favicon.ico',
            body: notification.message,
            badge: '/static/images/logo/favicon.ico',
            tag: 'petsona-notification',
            requireInteraction: false
        });
    }
}

// === REQUEST NOTIFICATION PERMISSION ===
function requestNotificationPermission() {
    if (!('Notification' in window)) return;
    
    if (Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

// ===== FETCH NOTIFICATIONS ON DROPDOWN CLICK ====
document.addEventListener('DOMContentLoaded', function() {
    // Wait for jQuery to be loaded
    function waitForJQuery(callback) {
        if (typeof $ !== 'undefined' && typeof jQuery !== 'undefined') {
            callback();
        } else {
            setTimeout(() => waitForJQuery(callback), 100);
        }
    }

    waitForJQuery(() => {
        // Inject aggressive CSS to force new design
        injectNotificationCSS();
        
        // Initialize Socket.IO when page loads
        initializeNotificationSocket();
        
        // Find the notifications dropdown trigger
        const notificationsDropdown = document.querySelector('[data-toggle="dropdown"][href="#"]');
        
        if (notificationsDropdown) {
            notificationsDropdown.addEventListener('click', function() {
                // Emit request to get notifications
                if (isSocketConnected && notificationSocket) {
                    notificationSocket.emit('get_notifications');
                }
            });
        }
        
        // Setup notification modal navigation buttons
        const prevBtn = document.getElementById('notifPrevBtn');
        const nextBtn = document.getElementById('notifNextBtn');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', function() {
                if (currentNotificationIndex > 0) {
                    currentNotificationIndex--;
                    displayNotificationModal(allNotifications[currentNotificationIndex]);
                }
            });
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', function() {
                if (currentNotificationIndex < allNotifications.length - 1) {
                    currentNotificationIndex++;
                    displayNotificationModal(allNotifications[currentNotificationIndex]);
                }
            });
        }
        
        // Request notification permission
        requestNotificationPermission();
        
        // Refresh notifications every 30 seconds
        setInterval(function() {
            if (isSocketConnected && notificationSocket) {
                notificationSocket.emit('get_unread_count');
            }
        }, 30000);
    });
});

// === MARK NOTIFICATION AS READ ===
function markNotificationAsRead(notificationId) {
    if (isSocketConnected && notificationSocket) {
        notificationSocket.emit('mark_notification_read', {
            notification_id: notificationId
        });
    }
}

// === MARK ALL AS READ ===
function markAllNotificationsAsRead() {
    if (isSocketConnected && notificationSocket) {
        notificationSocket.emit('mark_all_notifications_read');
    }
}

// === VIEW NOTIFICATION IN MODAL ===
function viewNotificationFull(notificationId) {
    console.log('📖 Opening notification modal for ID:', notificationId);
    
    // Find the notification in the current list
    const container = document.querySelector('.notifications-scroll-container');
    if (!container) return;
    
    // Get all notification items and find the one we're looking for
    const notificationItem = container.querySelector(`[data-notification-id="${notificationId}"]`);
    if (!notificationItem) {
        console.warn('Notification item not found in DOM');
        return;
    }
    
    // Try to get full notification data via Socket.IO if available
    if (isSocketConnected && notificationSocket) {
        // Emit request to get full notification details
        notificationSocket.emit('get_notification_detail', {
            notification_id: notificationId
        });
    } else {
        // Fallback: display what we have in the DOM
        displayNotificationModal(notificationItem);
    }
}

// === DISPLAY NOTIFICATION MODAL ===
function displayNotificationModal(notificationData) {
    console.log('🔍 Displaying notification modal:', notificationData);
    
    // Get modal elements
    const modal = document.getElementById('notificationModal');
    if (!modal) {
        console.warn('Notification modal not found in DOM');
        return;
    }
    
    // Extract data from notification object with proper defaults
    const title = notificationData.title || 'Notification';
    const message = notificationData.message || 'No message provided';
    const icon = notificationData.icon || 'fas fa-bell';
    const createdAt = notificationData.created_at || notificationData.time_full || notificationData.time || 'Just now';
    const isRead = notificationData.is_read || false;
    const notificationType = notificationData.type || 'info';
    const notificationId = notificationData.id;
    
    // Update modal header
    const headerIcon = document.getElementById('notifModalIcon');
    if (headerIcon) {
        headerIcon.className = icon;
    }
    
    const headerLabel = document.getElementById('notificationModalLabel');
    if (headerLabel) {
        headerLabel.textContent = title.replace(/[📌✅❌🎉📋⚠️💬🔐✏️🚫]/g, '').trim() || 'Notification Details';
    }
    
    const headerTime = document.getElementById('notifModalTime');
    if (headerTime) {
        headerTime.textContent = notificationData.time_short || notificationData.time || 'Recently';
    }
    
    // Update modal body
    const titleElement = document.getElementById('notifModalTitle');
    if (titleElement) {
        titleElement.textContent = title;
        titleElement.style.display = 'block !important';
        titleElement.style.visibility = 'visible !important';
    }
    
    const messageElement = document.getElementById('notifModalMessage');
    if (messageElement) {
        messageElement.textContent = message;
        messageElement.style.display = 'block !important';
        messageElement.style.visibility = 'visible !important';
        messageElement.style.whiteSpace = 'normal !important';
        messageElement.style.wordWrap = 'break-word !important';
    }
    
    const dateElement = document.getElementById('notifModalDateFull');
    if (dateElement) {
        // Format date to 12-hour format with AM/PM
        const formattedDate = format12HourTime(notificationData.created_at || notificationData.time_full || new Date());
        dateElement.textContent = formattedDate;
    }
    
    const typeElement = document.getElementById('notifModalType');
    if (typeElement) {
        typeElement.textContent = notificationType.charAt(0).toUpperCase() + notificationType.slice(1);
    }
    
    // Handle read status
    const readAtBlock = document.getElementById('notifReadAtBlock');
    if (readAtBlock) {
        if (notificationData.read_at) {
            readAtBlock.style.display = 'block !important';
            const readAtFormatted = format12HourTime(notificationData.read_at);
            const readAtElement = document.getElementById('notifModalReadAt');
            if (readAtElement) {
                readAtElement.textContent = readAtFormatted;
            }
        } else {
            readAtBlock.style.display = 'none !important';
        }
    }
    
    // Handle related resource
    const relatedBlock = document.getElementById('notifRelatedBlock');
    if (relatedBlock) {
        if (notificationData.related_type && notificationData.related_id) {
            relatedBlock.style.display = 'block !important';
            
            const relatedType = document.getElementById('notifRelatedType');
            if (relatedType) {
                relatedType.textContent = notificationData.related_type.charAt(0).toUpperCase() + notificationData.related_type.slice(1);
            }
            
            const relatedId = document.getElementById('notifRelatedId');
            if (relatedId) {
                relatedId.textContent = notificationData.related_id;
            }
        } else {
            relatedBlock.style.display = 'none !important';
        }
    }
    
    // Handle action link
    const actionLink = document.getElementById('notificationActionLink');
    if (actionLink) {
        if (notificationData.link) {
            actionLink.href = notificationData.link;
            actionLink.style.display = 'inline-block !important';
        } else {
            actionLink.style.display = 'none !important';
        }
    }
    
    // Update notification counter
    const currentCounter = document.getElementById('notifCurrent');
    const totalCounter = document.getElementById('notifTotal');
    if (currentCounter && totalCounter) {
        currentCounter.textContent = (currentNotificationIndex + 1) || 1;
        totalCounter.textContent = allNotifications.length || 1;
    }
    
    // Update navigation button states
    const prevBtn = document.getElementById('notifPrevBtn');
    const nextBtn = document.getElementById('notifNextBtn');
    if (prevBtn) {
        prevBtn.disabled = currentNotificationIndex <= 0;
        prevBtn.style.opacity = currentNotificationIndex <= 0 ? '0.5' : '1';
    }
    if (nextBtn) {
        nextBtn.disabled = currentNotificationIndex >= (allNotifications.length - 1);
        nextBtn.style.opacity = currentNotificationIndex >= (allNotifications.length - 1) ? '0.5' : '1';
    }
    
    // Handle mark as read button
    const markReadBtn = document.getElementById('notificationMarkReadBtn');
    if (markReadBtn) {
        if (isRead) {
            markReadBtn.innerHTML = '<i class="fas fa-check-double"></i> Already Read';
            markReadBtn.disabled = true;
            markReadBtn.style.opacity = '0.6';
        } else {
            markReadBtn.innerHTML = '<i class="fas fa-check"></i> Mark as Read';
            markReadBtn.disabled = false;
            markReadBtn.style.opacity = '1';
            markReadBtn.onclick = function() {
                markNotificationAsRead(notificationId);
                // Close modal after marking as read
                setTimeout(function() {
                    if (typeof $ !== 'undefined' && $.fn.modal) {
                        $('#notificationModal').modal('hide');
                    } else {
                        modal.style.display = 'none';
                    }
                }, 300);
            };
        }
    }
    
    // Set notification ID for delete operations
    setNotificationToDelete(notificationId);
    
    // Show modal with proper Bootstrap handling
    console.log('📖 Opening notification modal...');
    try {
        if (typeof $ !== 'undefined' && $.fn.modal) {
            // Ensure modal is properly set up
            const $modal = $('#notificationModal');
            $modal.modal({
                backdrop: 'static',
                keyboard: true,
                focus: true
            });
            $modal.modal('show');
            console.log('✅ Modal shown via Bootstrap');
        } else {
            // Fallback for non-Bootstrap environments
            modal.style.display = 'block';
            modal.style.zIndex = '10000';
            console.log('✅ Modal shown via direct display');
        }
    } catch (error) {
        console.error('❌ Error opening modal:', error);
        modal.style.display = 'block';
        modal.style.zIndex = '10000';
    }
    
    // Handle delete button
    const deleteBtn = document.getElementById('notifDeleteBtn');
    if (deleteBtn) {
        deleteBtn.onclick = function() {
            if (typeof $ !== 'undefined' && $.fn.modal) {
                $('#deleteNotificationConfirmModal').modal('show');
            }
        };
    }
}

// === DELETE NOTIFICATION ===
// Check if notificationToDelete already exists to prevent double-declaration
if (typeof notificationToDelete === 'undefined') {
    var notificationToDelete = null;
}

document.addEventListener('DOMContentLoaded', function() {
    // Confirm delete notification from modal
    const confirmDeleteBtn = document.getElementById('confirmDeleteNotifBtn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', async function() {
            if (!notificationToDelete) return;
            setButtonLoading(confirmDeleteBtn, true, 'Delete');
            
            try {
                const response = await fetch(`/api/notifications/${notificationToDelete}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    if (typeof $ !== 'undefined' && $.fn.modal) {
                        $('#deleteNotificationConfirmModal').modal('hide');
                        // Delay main modal close slightly to allow confirmation to close first
                        setTimeout(function() {
                            $('#notificationModal').modal('hide');
                        }, 200);
                    }
                    // Refresh notifications via socket update
                    if (notificationSocket) {
                        notificationSocket.emit('get_notifications');
                        notificationSocket.emit('get_unread_count');
                    }
                    showFlashMessage('Notification deleted successfully', 'success');
                } else {
                    showFlashMessage('Failed to delete notification', 'danger');
                }
            } catch (error) {
                console.error('Error deleting notification:', error);
                showFlashMessage('Error deleting notification', 'danger');
            } finally {
                setButtonLoading(confirmDeleteBtn, false, 'Delete');
            }
        });
    }
    
    // Delete all notifications
    const deleteAllBtn = document.getElementById('deleteAllNotificationsBtn');
    if (deleteAllBtn) {
        deleteAllBtn.addEventListener('click', function() {
            if (typeof $ !== 'undefined' && $.fn.modal) {
                $('#deleteAllNotificationsModal').modal('show');
            }
        });
    }
    
    // Confirm delete all notifications
    const confirmDeleteAllBtn = document.getElementById('confirmDeleteAllNotifBtn');
    if (confirmDeleteAllBtn) {
        confirmDeleteAllBtn.addEventListener('click', async function() {
            setButtonLoading(confirmDeleteAllBtn, true, 'Delete all');

            try {
                const response = await fetch('/api/notifications/delete-all', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    if (typeof $ !== 'undefined' && $.fn.modal) {
                        $('#deleteAllNotificationsModal').modal('hide');
                        // Delay main modal close slightly to allow confirmation to close first
                        setTimeout(function() {
                            $('#notificationModal').modal('hide');
                        }, 200);
                    }
                    // Refresh notifications via socket update
                    if (notificationSocket) {
                        notificationSocket.emit('get_notifications');
                        notificationSocket.emit('get_unread_count');
                    }
                    showFlashMessage('All notifications deleted successfully', 'success');
                } else {
                    showFlashMessage('Failed to delete notifications', 'danger');
                }
            } catch (error) {
                console.error('Error deleting all notifications:', error);
                showFlashMessage('Error deleting notifications', 'danger');
            } finally {
                setButtonLoading(confirmDeleteAllBtn, false, 'Delete all');
            }
        });
    }
});

// Store notification ID when delete is clicked (called from modal)
function setNotificationToDelete(notificationId) {
    notificationToDelete = notificationId;
}

function setButtonLoading(button, isLoading, defaultLabel) {
    if (!button) return;
    const spinner = button.querySelector('.spinner-border');
    const btnText = button.querySelector('.btn-text');

    button.disabled = isLoading;
    button.setAttribute('aria-busy', isLoading ? 'true' : 'false');

    if (spinner) {
        spinner.classList.toggle('d-none', !isLoading);
    }

    if (btnText) {
        btnText.textContent = defaultLabel;
    }

    if (isLoading) {
        button.classList.add('disabled', 'opacity-75');
    } else {
        button.classList.remove('disabled', 'opacity-75');
    }
}

function showFlashMessage(message, category = 'success') {
    const container = document.querySelector('.flash-container');
    if (!container) return;

    const flash = document.createElement('div');
    flash.className = `flash flash-${category}`;
    flash.dataset.dismissTime = '6400';
    flash.style.animation = 'flashSlideIn 0.3s ease-out';

    const icon = category === 'success'
        ? '<i class="fas fa-check-circle"></i>'
        : category === 'danger'
            ? '<i class="fas fa-times-circle"></i>'
            : category === 'warning'
                ? '<i class="fas fa-exclamation-triangle"></i>'
                : '<i class="fas fa-info-circle"></i>';

    flash.innerHTML = `
        <div class="flash-icon">${icon}</div>
        <div class="flash-content">${message}</div>
        <button class="flash-close" aria-label="Close notification">
          <i class="fas fa-times"></i>
        </button>
    `;

    container.appendChild(flash);

    const removeFlash = () => {
        flash.style.animation = 'flashSlideOut 0.4s ease-in forwards';
        setTimeout(() => flash.remove(), 400);
    };

    flash.querySelector('.flash-close')?.addEventListener('click', removeFlash);
    setTimeout(removeFlash, 6400);
}

function showSuccessMessage(message) {
    showFlashMessage(message, 'success');
}

function showErrorMessage(message) {
    showFlashMessage(message, 'danger');
}

// === HELPER: Generate color from name ===
function getColorFromName(name) {
    const colors = [
        '#667eea', '#764ba2', '#f093fb', '#4facfe',
        '#43e97b', '#fa709a', '#fee140', '#30b0fe',
        '#a8edea', '#fed6e3', '#ff9a56', '#a1c4fd'
    ];
    
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    return colors[Math.abs(hash) % colors.length];
}
