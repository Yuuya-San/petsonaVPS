"""
Suspicious Activity Detection System for Admin Alerts

This module monitors audit logs for security-critical patterns and 
alerts admins automatically when suspicious activities are detected.

Suspicious Pattern Categories:
1. Account Compromise Indicators
2. Brute Force Attempts
3. 2FA Manipulation
4. Unauthorized Access
5. Fraud Patterns
"""

from app.models import AuditLog, User
from app.extensions import db, socketio
from datetime import datetime, timedelta
import pytz
from sqlalchemy import and_, or_
import logging

logger = logging.getLogger(__name__)
PH_TZ = pytz.timezone('Asia/Manila')


class SuspiciousActivityDetector:
    """Detects suspicious patterns in audit logs and creates admin alerts"""
    
    # Configuration for suspicious activity thresholds
    SUSPICIOUS_PATTERNS = {
        # Failed login attempts: 5+ failures in 15 minutes
        'failed_logins': {
            'events': ['user.login_failed', 'admin.login_failed'],
            'threshold': 5,
            'time_window_minutes': 15,
            'severity': 'high',
            'action': 'auto_lock_account',
            'alert_type': 'account_compromise_attempt'
        },
        
        # 2FA failures: 3+ failures in 10 minutes
        '2fa_bypass_attempt': {
            'events': ['user.login_failed_2fa'],
            'threshold': 3,
            'time_window_minutes': 10,
            'severity': 'critical',
            'action': 'reset_2fa_and_notify',
            'alert_type': '2fa_manipulation'
        },
        
        # Email change + password reset within 5 minutes (account compromise indicator)
        'email_password_reset_sequence': {
            'events': ['user.email_changed', 'user.password_reset_success'],
            'threshold': 1,  # Single occurrence is suspicious
            'time_window_minutes': 5,
            'severity': 'critical',
            'action': 'freeze_account_and_notify',
            'alert_type': 'potential_account_compromise'
        },
        
        # Multiple failed login attempts followed by successful login (credential stuffing)
        'failed_then_success_login': {
            'events': ['user.login_failed', 'user.login_success'],
            'threshold': 3,  # 3 fails before 1 success
            'time_window_minutes': 10,
            'severity': 'high',
            'action': 'notify_admin_and_user',
            'alert_type': 'credential_stuffing'
        },
        
        # reCAPTCHA failures: 5+ in 20 minutes (bot detection)
        'recaptcha_failures': {
            'events': ['user.login_failed', 'admin.login_failed'],
            'filter_by_detail': 'reason=recaptcha_failed',
            'threshold': 5,
            'time_window_minutes': 20,
            'severity': 'medium',
            'action': 'notify_admin',
            'alert_type': 'bot_detection'
        },
        
        # Multiple account lockouts: 3+ different users in 15 minutes (possible attack)
        'mass_account_lockouts': {
            'events': ['user.account_locked', 'admin.account_locked'],
            'threshold': 3,
            'time_window_minutes': 15,
            'severity': 'critical',
            'action': 'security_alert_all_admins',
            'alert_type': 'distributed_attack'
        },
        
        # User role elevation by non-superadmin (unauthorized privilege escalation)
        'unauthorized_role_elevation': {
            'events': ['user.role_changed_to_admin', 'user.role_changed_to_merchant'],
            'check': 'actor_is_not_superadmin',
            'severity': 'critical',
            'action': 'freeze_action_notify_admins',
            'alert_type': 'privilege_escalation_attempt'
        },
        
        # Google OAuth login with changed email within 24 hours
        'oauth_account_takeover': {
            'events': ['user.login_google', 'user.email_changed'],
            'threshold': 1,
            'time_window_minutes': 1440,  # 24 hours
            'severity': 'high',
            'action': 'verify_user_identity',
            'alert_type': 'oauth_account_takeover'
        },
        
        # Review bombing: 5+ reviews in 1 hour (coordination/spam)
        'review_bombing': {
            'events': ['booking.review_submitted'],
            'threshold': 5,
            'time_window_minutes': 60,
            'severity': 'medium',
            'action': 'flag_reviews_for_moderation',
            'alert_type': 'review_spam'
        },
        
        # Multiple merchant applications from same IP/device in 1 hour (fraud ring)
        'merchant_application_spam': {
            'events': ['merchant.application_submitted'],
            'threshold': 3,
            'time_window_minutes': 60,
            'severity': 'high',
            'action': 'flag_applications',
            'alert_type': 'merchant_fraud_ring'
        },
        
        # Password reset token reuse attempts (brute force)
        'password_reset_token_reuse': {
            'events': ['user.password_reset_invalid_token', 'user.password_reset_expired'],
            'threshold': 5,
            'time_window_minutes': 30,
            'severity': 'medium',
            'action': 'invalidate_all_tokens',
            'alert_type': 'token_brute_force'
        },
        
        # Booking no-show appeals spam: 3+ appeals in 30 days
        'no_show_appeal_spam': {
            'events': ['booking.appeal_no_show_submitted'],
            'threshold': 3,
            'time_window_minutes': 43200,  # 30 days
            'severity': 'low',
            'action': 'review_user_appeal_history',
            'alert_type': 'appeal_abuse'
        },
        
        # Message blocking abuse: 10+ blocks in 1 hour
        'message_block_spam': {
            'events': ['message.conversation_blocked'],
            'threshold': 10,
            'time_window_minutes': 60,
            'severity': 'low',
            'action': 'review_blocking_pattern',
            'alert_type': 'block_spam'
        },
        
        # Rapid merchant store updates: 20+ updates in 1 hour
        'rapid_store_updates': {
            'events': ['merchant.store_updated'],
            'threshold': 20,
            'time_window_minutes': 60,
            'severity': 'low',
            'action': 'rate_limit_updates',
            'alert_type': 'rapid_api_activity'
        }
    }
    
    @classmethod
    def check_all_patterns(cls):
        """Check all registered suspicious patterns against audit logs
        
        Called periodically (e.g., every 5 minutes) to detect suspicious activity
        """
        alerts_created = []
        
        for pattern_name, pattern_config in cls.SUSPICIOUS_PATTERNS.items():
            try:
                alert = cls.check_pattern(pattern_name, pattern_config)
                if alert:
                    alerts_created.append(alert)
            except Exception as e:
                logger.error(f"[SUSPICIOUS ACTIVITY] Error checking pattern '{pattern_name}': {str(e)}")
        
        return alerts_created
    
    @classmethod
    def check_pattern(cls, pattern_name, pattern_config):
        """Check a specific suspicious activity pattern
        
        Args:
            pattern_name: Name of the pattern
            pattern_config: Configuration dict with detection rules
            
        Returns:
            Admin alert dict if pattern detected, None otherwise
        """
        try:
            events = pattern_config.get('events', [])
            threshold = pattern_config.get('threshold', 1)
            time_window = pattern_config.get('time_window_minutes', 15)
            severity = pattern_config.get('severity', 'medium')
            
            cutoff_time = datetime.now(PH_TZ) - timedelta(minutes=time_window)
            
            # Query audit logs matching the pattern
            query = AuditLog.query.filter(
                and_(
                    AuditLog.event.in_(events),
                    AuditLog.timestamp >= cutoff_time,
                    AuditLog.deleted_at.is_(None)
                )
            )
            
            logs = query.all()
            
            # Check if threshold exceeded
            if len(logs) >= threshold:
                return cls.create_admin_alert(
                    pattern_name=pattern_name,
                    severity=severity,
                    logs=logs,
                    pattern_config=pattern_config
                )
        
        except Exception as e:
            logger.error(f"[SUSPICIOUS ACTIVITY] Error in check_pattern for '{pattern_name}': {str(e)}")
        
        return None
    
    @classmethod
    def create_admin_alert(cls, pattern_name, severity, logs, pattern_config):
        """Create an admin alert notification for suspicious activity
        
        Args:
            pattern_name: Pattern that was triggered
            severity: Alert severity level (low/medium/high/critical)
            logs: List of suspicious audit logs
            pattern_config: Pattern configuration
            
        Returns:
            Admin alert data
        """
        from app.utils.notification_manager import NotificationManager
        
        try:
            # Get all admin users
            admins = User.query.filter_by(role='admin', is_active=True).all()
            
            if not admins:
                logger.warning(f"[SUSPICIOUS ACTIVITY] No admin users found to alert")
                return None
            
            # Create alert message
            event_counts = {}
            affected_users = set()
            
            for log in logs:
                event_counts[log.event] = event_counts.get(log.event, 0) + 1
                if log.actor_id:
                    affected_users.add(log.actor_id)
            
            user_list = ", ".join([str(uid) for uid in list(affected_users)[:5]])
            if len(affected_users) > 5:
                user_list += f", +{len(affected_users) - 5} more"
            
            title = f"🚨 {severity.upper()} SECURITY ALERT: {pattern_name.replace('_', ' ').title()}"
            message = f"Detected suspicious activity: {len(logs)} events in {pattern_config.get('time_window_minutes')} minutes. Affected users: {user_list}"
            
            # Emit to all admins
            alert_data = {
                'pattern_name': pattern_name,
                'severity': severity,
                'event_count': len(logs),
                'affected_users': list(affected_users),
                'time_window_minutes': pattern_config.get('time_window_minutes'),
                'logs': [
                    {
                        'id': log.id,
                        'event': log.event,
                        'actor_id': log.actor_id,
                        'actor_email': log.actor_email,
                        'timestamp': log.timestamp.isoformat(),
                        'details': log.details
                    }
                    for log in logs[:10]  # Include first 10 logs
                ]
            }
            
            for admin in admins:
                NotificationManager.create_and_emit(
                    user_id=admin.id,
                    title=title,
                    message=message,
                    notification_type='security_alert',
                    related_id=logs[0].id if logs else None,
                    related_type='audit_log'
                )
                
                # Emit via SocketIO for real-time alert
                socketio.emit('security_alert', alert_data, room=f"user_{admin.id}")
            
            logger.warning(f"[SUSPICIOUS ACTIVITY] ⚠️ Alert created for pattern: {pattern_name}")
            return alert_data
            
        except Exception as e:
            logger.error(f"[SUSPICIOUS ACTIVITY] Error creating admin alert: {str(e)}")
            return None
    
    @classmethod
    def get_user_activity_summary(cls, user_id, days=7):
        """Get summary of user activity for risk assessment
        
        Args:
            user_id: User ID to check
            days: Number of days to look back
            
        Returns:
            Dictionary with user activity metrics
        """
        cutoff_time = datetime.now(PH_TZ) - timedelta(days=days)
        
        logs = AuditLog.query.filter(
            and_(
                AuditLog.actor_id == user_id,
                AuditLog.timestamp >= cutoff_time,
                AuditLog.deleted_at.is_(None)
            )
        ).all()
        
        event_counts = {}
        failed_logins = 0
        successful_logins = 0
        
        for log in logs:
            event_counts[log.event] = event_counts.get(log.event, 0) + 1
            
            if 'login_failed' in log.event:
                failed_logins += 1
            elif 'login_success' in log.event:
                successful_logins += 1
        
        risk_score = cls.calculate_risk_score(
            failed_logins=failed_logins,
            successful_logins=successful_logins,
            total_events=len(logs),
            event_types=len(event_counts)
        )
        
        return {
            'user_id': user_id,
            'total_events': len(logs),
            'failed_logins': failed_logins,
            'successful_logins': successful_logins,
            'event_types': event_counts,
            'risk_score': risk_score,
            'time_period_days': days
        }
    
    @staticmethod
    def calculate_risk_score(failed_logins, successful_logins, total_events, event_types):
        """Calculate a risk score (0-100) for a user
        
        High risk score indicates suspicious activity pattern
        """
        score = 0
        
        # High failed login ratio is risky
        if successful_logins > 0:
            failure_ratio = failed_logins / (failed_logins + successful_logins)
            if failure_ratio > 0.5:
                score += 30
        elif failed_logins > 3:
            score += 40
        
        # Unusual activity frequency
        if total_events > 100:
            score += 15
        elif total_events < 2:
            score += 5  # Very low activity
        
        # Unusual event type diversity
        if event_types > 20:
            score += 20
        
        return min(score, 100)


def check_suspicious_activity_periodically():
    """Background task to check for suspicious activities
    
    Can be called by a background task runner (APScheduler, Celery, etc.)
    every 5 minutes or as needed
    """
    try:
        alerts = SuspiciousActivityDetector.check_all_patterns()
        if alerts:
            logger.info(f"[SUSPICIOUS ACTIVITY] Detected {len(alerts)} suspicious patterns")
        return alerts
    except Exception as e:
        logger.error(f"[SUSPICIOUS ACTIVITY] Error in periodic check: {str(e)}")
        return []
