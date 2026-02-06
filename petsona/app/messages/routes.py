"""Routes for messaging functionality."""
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from . import bp
from .forms import SendMessageForm, ReportMessageForm, BlockUserForm
from app.models import User
from app.models.message import Message, Conversation
from app.extensions import db, csrf
from app.utils.messaging import (
    get_or_create_conversation,
    create_message,
    get_user_inbox,
    get_conversation_messages,
    mark_conversation_messages_as_read,
    block_user,
    unblock_user,
    archive_conversation,
    unarchive_conversation,
    delete_message_for_user,
    report_message,
    get_unread_count,
    format_time_ago,
    is_user_blocked
)
from app.utils.audit import log_event
import logging

logger = logging.getLogger(__name__)


@bp.route('/inbox', methods=['GET'])
@login_required
def inbox():
    """Display user's message inbox."""
    page = request.args.get('page', 1, type=int)
    tab = request.args.get('tab', 'all', type=str)
    
    if tab == 'archived':
        pagination = get_user_inbox(current_user.id, page=page, per_page=20, include_archived=True)
        conversations = [conv for conv in pagination.items 
                        if (conv.user1_id == current_user.id and conv.is_archived_by_user1) or 
                           (conv.user2_id == current_user.id and conv.is_archived_by_user2)]
    else:
        pagination = get_user_inbox(current_user.id, page=page, per_page=20, include_archived=False)
        conversations = pagination.items
    
    # Get total unread count
    unread_count = get_unread_count(current_user.id)
    
    return render_template(
        'messages/inbox.html',
        conversations=conversations,
        unread_count=unread_count,
        tab=tab,
        pagination=pagination,
        page_title="Messages"
    )


@bp.route('/conversation/<int:conversation_id>', methods=['GET'])
@login_required
def conversation(conversation_id):
    """Display a specific conversation."""
    conversation_obj = Conversation.query.get(conversation_id)
    
    if not conversation_obj:
        flash('Conversation not found.', 'danger')
        return redirect(url_for('messages.inbox'))
    
    # Check if user is part of this conversation
    if conversation_obj.user1_id != current_user.id and conversation_obj.user2_id != current_user.id:
        flash('You do not have access to this conversation.', 'danger')
        return redirect(url_for('messages.inbox'))
    
    # Check if user is blocked
    if conversation_obj.is_blocked_for_user(current_user.id):
        flash('You have blocked this conversation.', 'warning')
        return redirect(url_for('messages.inbox'))
    
    # Get other user
    other_user = conversation_obj.get_other_user(current_user.id)
    
    page = request.args.get('page', 1, type=int)
    pagination = get_conversation_messages(conversation_id, current_user.id, page=page, per_page=50)
    messages = pagination.items
    
    # Mark messages as read
    mark_conversation_messages_as_read(conversation_id, current_user.id)
    
    # Get all conversations for left sidebar
    all_conversations_paginated = get_user_inbox(current_user.id, page=1, per_page=50, include_archived=False)
    all_conversations = all_conversations_paginated.items
    
    form = SendMessageForm()
    
    return render_template(
        'messages/conversation.html',
        conversation=conversation_obj,
        messages=messages,
        other_user=other_user,
        all_conversations=all_conversations,
        form=form,
        pagination=pagination,
        page_title=f"Chat with {other_user.first_name}"
    )


@bp.route('/send-message/<int:conversation_id>', methods=['POST'])
@csrf.exempt
@login_required
def send_message(conversation_id):
    """Send a message in a conversation."""
    try:
        logger.info(f"================== SEND MESSAGE REQUEST ==================")
        logger.info(f"Conversation ID from URL: {conversation_id}")
        logger.info(f"Current user ID: {current_user.id}")
        
        conversation_obj = Conversation.query.get(conversation_id)
        
        if not conversation_obj:
            logger.warning(f"❌ Conversation {conversation_id} not found")
            return jsonify({'error': 'Conversation not found'}), 404
        
        logger.info(f"✅ Found conversation {conversation_id}: user1={conversation_obj.user1_id}, user2={conversation_obj.user2_id}")
        
        # Verify user is part of conversation
        if conversation_obj.user1_id != current_user.id and conversation_obj.user2_id != current_user.id:
            logger.warning(f"❌ User {current_user.id} not part of conversation {conversation_id}")
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if blocked
        if conversation_obj.is_blocked_for_user(current_user.id):
            logger.warning(f"❌ User {current_user.id} is blocked in conversation {conversation_id}")
            return jsonify({'error': 'You are blocked from sending messages in this conversation'}), 403
        
        # Get JSON data
        data = request.get_json()
        
        if not data or 'content' not in data:
            logger.warning("❌ Missing message content in request")
            return jsonify({'error': 'Message content is required'}), 400
        
        content = data.get('content', '').strip()
        
        # Validate content
        if not content:
            logger.warning("❌ Empty message content after strip")
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        if len(content) > 5000:
            logger.warning(f"❌ Message too long: {len(content)} chars")
            return jsonify({'error': 'Message is too long (max 5000 characters)'}), 400
        
        receiver_id = conversation_obj.get_other_user_id(current_user.id)
        logger.info(f"📤 Determined receiver_id: {receiver_id} (other user in conversation {conversation_id})")
        
        logger.info(f"📝 Creating message in conversation {conversation_id} from user {current_user.id} to {receiver_id}")
        message = create_message(
            conversation_id=conversation_id,
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content
        )
        
        if not message:
            logger.error(f"❌ Failed to create message in conversation {conversation_id}")
            return jsonify({'error': 'Failed to send message'}), 500
        
        logger.info(f"✅ MESSAGE CREATED:")
        logger.info(f"   Message ID: {message.id}")
        logger.info(f"   Conversation ID: {message.conversation_id}")
        logger.info(f"   From user: {message.sender_id}")
        logger.info(f"   To user: {message.receiver_id}")
        logger.info(f"   Content length: {len(message.content)}")
        
        log_event(
            event='message.sent',
            details={'message_id': message.id, 'to_user': receiver_id}
        )
        
        # Emit Socket.IO event for real-time delivery to all in conversation room
        from app.extensions import socketio
        room = f'conversation_{conversation_id}'
        
        # Build sender photo URL
        sender_photo = None
        if message.sender and message.sender.photo_url:
            try:
                sender_photo = url_for('static', filename=message.sender.photo_url, _external=False)
            except:
                sender_photo = None
        
        # Emit message to all users in the conversation room
        socketio.emit(
            'new_message',
            {
                'id': message.id,
                'sender_id': message.sender_id,
                'receiver_id': message.receiver_id,
                'sender_name': message.sender.first_name if message.sender else 'Unknown',
                'sender_photo': sender_photo,
                'content': message.content,
                'is_read': message.is_read,
                'is_delivered': message.is_delivered,
                'created_at': message.created_at.isoformat(),
                'read_at': message.read_at.isoformat() if message.read_at else None,
                'created_at_formatted': message.get_time_only(),
                'created_at_formatted_full': message.get_formatted_time(),
                'conversation_id': conversation_id,
            },
            room=room
        )
        
        # Broadcast navbar update to receiver
        from app.socket_events import broadcast_message_to_navbar, notify_unread_message_count
        message_preview = content[:50] + ('...' if len(content) > 50 else '')
        broadcast_message_to_navbar(
            recipient_id=receiver_id,
            conversation_id=conversation_id,
            sender_id=current_user.id,
            sender_name=current_user.first_name,
            sender_avatar=sender_photo,
            message_preview=message_preview
        )
        
        # Notify receiver of updated unread count
        new_unread_count = get_unread_count(receiver_id)
        notify_unread_message_count(receiver_id, new_unread_count)
        
        return jsonify({
            'success': True,
            'message': message.to_dict(current_user.id)
        })
    except Exception as e:
        logger.error(f"❌ Error in send_message: {str(e)}", exc_info=True)
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@bp.route('/mark-read/<int:message_id>', methods=['POST'])
@csrf.exempt
@login_required
def mark_read(message_id):
    """Mark a specific message as read."""
    try:
        message = Message.query.get(message_id)
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        # Verify user is receiver
        if message.receiver_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        message.mark_as_read()
        
        # Emit Socket.IO event
        from app.extensions import socketio
        from app.socket_events import notify_unread_message_count
        socketio.emit(
            'message_read',
            {'message_id': message.id, 'read_at': message.read_at.isoformat()},
            room=f'conversation_{message.conversation_id}'
        )
        
        # Notify sender of updated unread count for their view
        new_unread_count = get_unread_count(current_user.id)
        notify_unread_message_count(current_user.id, new_unread_count)
        
        return jsonify({'success': True, 'read_at': message.read_at.isoformat()})
    except Exception as e:
        logger.error(f"Error marking message as read: {str(e)}")
        return jsonify({'error': 'Failed to mark message as read'}), 500


@bp.route('/delete-message/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    """Delete a message for the current user (soft delete)."""
    message = Message.query.get(message_id)
    
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    # Verify user is sender or receiver
    if message.sender_id != current_user.id and message.receiver_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if delete_message_for_user(message_id, current_user.id):
        log_event(
            event='message.deleted',
            details={'message_id': message_id}
        )
        return jsonify({'success': True})
    
    return jsonify({'error': 'Failed to delete message'}), 500


@bp.route('/report-message/<int:message_id>', methods=['GET', 'POST'])
@login_required
def report_message_route(message_id):
    """Report a message."""
    message = Message.query.get(message_id)
    
    if not message:
        flash('Message not found.', 'danger')
        return redirect(url_for('messages.inbox'))
    
    # Prevent self-reporting
    if message.sender_id == current_user.id:
        flash('You cannot report your own messages.', 'warning')
        return redirect(url_for('messages.conversation', conversation_id=message.conversation_id))
    
    form = ReportMessageForm()
    
    if form.validate_on_submit():
        if report_message(message_id, current_user.id, form.reason.data, form.details.data):
            flash('Thank you for reporting this message. Our team will review it shortly.', 'success')
            log_event(
                event='message.reported',
                details={'message_id': message_id, 'reason': form.reason.data}
            )
            return redirect(url_for('messages.conversation', conversation_id=message.conversation_id))
        else:
            flash('Failed to report message.', 'danger')
    
    return render_template(
        'messages/report_message.html',
        message=message,
        form=form,
        page_title="Report Message"
    )


@bp.route('/block-user/<int:conversation_id>', methods=['POST'])
@login_required
def block_user_route(conversation_id):
    """Block a user from a conversation."""
    conversation_obj = Conversation.query.get(conversation_id)
    
    if not conversation_obj:
        return jsonify({'error': 'Conversation not found'}), 404
    
    # Verify user is part of conversation
    if conversation_obj.user1_id != current_user.id and conversation_obj.user2_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    other_user_id = conversation_obj.get_other_user_id(current_user.id)
    
    if block_user(current_user.id, other_user_id, conversation_id):
        log_event(
            event='user.blocked',
            details={'blocked_user': other_user_id, 'conversation': conversation_id}
        )
        return jsonify({'success': True, 'message': 'User blocked'})
    
    return jsonify({'error': 'Failed to block user'}), 500


@bp.route('/unblock-user/<int:conversation_id>', methods=['POST'])
@login_required
def unblock_user_route(conversation_id):
    """Unblock a user in a conversation."""
    conversation_obj = Conversation.query.get(conversation_id)
    
    if not conversation_obj:
        return jsonify({'error': 'Conversation not found'}), 404
    
    # Verify user is part of conversation
    if conversation_obj.user1_id != current_user.id and conversation_obj.user2_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if unblock_user(current_user.id, conversation_id):
        log_event(
            event='user.unblocked',
            details={'conversation': conversation_id}
        )
        return jsonify({'success': True, 'message': 'User unblocked'})
    
    return jsonify({'error': 'Failed to unblock user'}), 500


@bp.route('/archive/<int:conversation_id>', methods=['POST'])
@login_required
def archive(conversation_id):
    """Archive a conversation."""
    conversation_obj = Conversation.query.get(conversation_id)
    
    if not conversation_obj:
        return jsonify({'error': 'Conversation not found'}), 404
    
    # Verify user is part of conversation
    if conversation_obj.user1_id != current_user.id and conversation_obj.user2_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if archive_conversation(current_user.id, conversation_id):
        log_event(
            event='conversation.archived',
            details={'conversation': conversation_id}
        )
        return jsonify({'success': True})
    
    return jsonify({'error': 'Failed to archive conversation'}), 500


@bp.route('/unarchive/<int:conversation_id>', methods=['POST'])
@login_required
def unarchive(conversation_id):
    """Unarchive a conversation."""
    conversation_obj = Conversation.query.get(conversation_id)
    
    if not conversation_obj:
        return jsonify({'error': 'Conversation not found'}), 404
    
    # Verify user is part of conversation
    if conversation_obj.user1_id != current_user.id and conversation_obj.user2_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if unarchive_conversation(current_user.id, conversation_id):
        log_event(
            event='conversation.unarchived',
            details={'conversation': conversation_id}
        )
        return jsonify({'success': True})
    
    return jsonify({'error': 'Failed to unarchive conversation'}), 500


@bp.route('/start-chat/<int:user_id>', methods=['GET'])
@login_required
def start_chat(user_id):
    """Start a new conversation with a user."""
    other_user = User.query.get(user_id)
    
    if not other_user:
        flash('User not found.', 'danger')
        return redirect(request.referrer or url_for('messages.inbox'))
    
    # Prevent messaging self
    if other_user.id == current_user.id:
        flash('You cannot message yourself.', 'warning')
        return redirect(url_for('messages.inbox'))
    
    # Get or create conversation
    conversation = get_or_create_conversation(current_user.id, other_user.id)
    
    log_event(
        event='conversation.started',
        details={'with_user': other_user.id}
    )
    
    return redirect(url_for('messages.conversation', conversation_id=conversation.id))


@bp.route('/api/unread-count', methods=['GET'])
@login_required
def get_unread_count_api():
    """Get unread message count via API."""
    count = get_unread_count(current_user.id)
    return jsonify({'unread_count': count})


@bp.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations_api():
    """Get user's conversations as JSON."""
    page = request.args.get('page', 1, type=int)
    tab = request.args.get('tab', 'all', type=str)
    
    pagination = get_user_inbox(current_user.id, page=page, per_page=20, include_archived=(tab == 'archived'))
    
    conversations_data = [conv.to_dict(current_user.id) for conv in pagination.items]
    
    return jsonify({
        'conversations': conversations_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })

@bp.route('/upload-file/<int:conversation_id>', methods=['POST'])
@login_required
def upload_file(conversation_id):
    """Upload a file to a conversation."""
    try:
        conversation_obj = Conversation.query.get(conversation_id)
        
        if not conversation_obj:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # Verify user is part of conversation
        if conversation_obj.user1_id != current_user.id and conversation_obj.user2_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if user is blocked
        if conversation_obj.is_blocked_for_user(current_user.id):
            return jsonify({'error': 'You are blocked from sending files in this conversation'}), 403
        
        # Check if file was provided
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        file_type = request.form.get('type', 'file')  # 'photo' or 'file'
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # ==================== SECURITY VALIDATIONS ====================
        
        import os
        from werkzeug.utils import secure_filename
        import mimetypes
        
        # 1. Validate MIME type
        allowed_mime_types = {
            'photo': ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
            'file': [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'application/zip',
                'application/x-rar-compressed'
            ]
        }
        
        file_mime_type = mimetypes.guess_type(file.filename)[0] or file.content_type
        if file_mime_type not in allowed_mime_types.get(file_type, []):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # 2. Validate file extension
        filename = secure_filename(file.filename)
        if not filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        valid_extensions = {
            'photo': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
            'file': ['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar']
        }
        
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if file_ext not in valid_extensions.get(file_type, []):
            return jsonify({'error': 'Invalid file extension'}), 400
        
        # 3. Validate file size
        max_file_sizes = {
            'photo': 5 * 1024 * 1024,  # 5MB for photos
            'file': 25 * 1024 * 1024   # 25MB for files
        }
        
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > max_file_sizes.get(file_type, 25 * 1024 * 1024):
            return jsonify({'error': 'File exceeds maximum size limit'}), 400
        
        if file_size == 0:
            return jsonify({'error': 'File is empty'}), 400
        
        # 4. Read and check file content (magic bytes)
        file_content = file.read(512)  # Read first 512 bytes for validation
        file.seek(0)
        
        # Check for executable or suspicious content
        suspicious_signatures = [b'MZ', b'BZh', b'7z', b'\x7fELF']  # Common executable signatures
        for sig in suspicious_signatures:
            if file_content.startswith(sig):
                return jsonify({'error': 'File type not allowed'}), 400
        
        # Create upload directory
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads/messages')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Ensure upload_dir is safe (prevent path traversal)
        upload_dir_abs = os.path.abspath(upload_dir)
        
        # Generate secure filename with timestamp
        import time
        import secrets
        timestamp = int(time.time())
        random_suffix = secrets.token_hex(4)  # Add random suffix for extra security
        filename_with_timestamp = f"{timestamp}_{random_suffix}_{filename}"
        filepath = os.path.join(upload_dir_abs, filename_with_timestamp)
        
        # Verify filepath is within upload directory (prevent directory traversal)
        filepath_abs = os.path.abspath(filepath)
        if not filepath_abs.startswith(upload_dir_abs):
            return jsonify({'error': 'Invalid file path'}), 400
        
        # Save file
        try:
            file.save(filepath)
            # Set proper file permissions (read-only for upload directory)
            os.chmod(filepath, 0o644)
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            return jsonify({'error': 'Failed to save file'}), 500
        
        # Return file URL for insertion
        return jsonify({
            'success': True,
            'filename': filename,
            'url': f'/static/uploads/messages/{filename_with_timestamp}',
            'type': file_type
        })
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({'error': 'Failed to upload file'}), 500