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
    
    form = SendMessageForm()
    
    return render_template(
        'messages/conversation.html',
        conversation=conversation_obj,
        messages=messages,
        other_user=other_user,
        form=form,
        pagination=pagination,
        page_title=f"Chat with {other_user.first_name}"
    )


@bp.route('/send-message/<int:conversation_id>', methods=['POST'])
@csrf.exempt
@login_required
def send_message(conversation_id):
    """Send a message in a conversation."""
    conversation_obj = Conversation.query.get(conversation_id)
    
    if not conversation_obj:
        return jsonify({'error': 'Conversation not found'}), 404
    
    # Verify user is part of conversation
    if conversation_obj.user1_id != current_user.id and conversation_obj.user2_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Check if blocked
    if conversation_obj.is_blocked_for_user(current_user.id):
        return jsonify({'error': 'You are blocked from sending messages in this conversation'}), 403
    
    # Get JSON data
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'Message content is required'}), 400
    
    content = data.get('content', '').strip()
    
    # Validate content
    if not content:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    if len(content) > 5000:
        return jsonify({'error': 'Message is too long (max 5000 characters)'}), 400
    
    receiver_id = conversation_obj.get_other_user_id(current_user.id)
    
    message = create_message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content
    )
    
    if message:
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
                'created_at_formatted': message.created_at.strftime('%I:%M %p'),
                'conversation_id': conversation_id,
            },
            room=room
        )
        
        return jsonify({
            'success': True,
            'message': message.to_dict(current_user.id)
        })
    else:
        return jsonify({'error': 'Failed to send message'}), 500


@bp.route('/mark-read/<int:message_id>', methods=['POST'])
@login_required
def mark_read(message_id):
    """Mark a specific message as read."""
    message = Message.query.get(message_id)
    
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    # Verify user is receiver
    if message.receiver_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    message.mark_as_read()
    
    # Emit Socket.IO event
    from app.extensions import socketio
    socketio.emit(
        'message_read',
        {'message_id': message.id, 'read_at': message.read_at.isoformat()},
        room=f'conversation_{message.conversation_id}'
    )
    
    return jsonify({'success': True, 'read_at': message.read_at.isoformat()})


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
