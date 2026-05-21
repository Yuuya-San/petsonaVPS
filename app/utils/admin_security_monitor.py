"""
Integration module for suspicious activity monitoring and admin alerts

This module integrates the suspicious activity detector with the notification system
to automatically alert admins of security threats and anomalous behavior.
"""

from app.utils.suspicious_activity_detector import SuspiciousActivityDetector
from app.utils.notification_manager import NotificationManager
from app.models import User, AuditLog
from app import db
import logging
from datetime import datetime, timedelta
import pytz
from sqlalchemy import and_

logger = logging.getLogger(__name__)
PH_TZ = pytz.timezone('Asia/Manila')


class AdminSecurityMonitor:
    """Monitors system security and sends admin alerts for suspicious activities"""
    
    @staticmethod
    def scan_and_alert_on_suspicious_activities():
        """
        Perform comprehensive security scan and alert admins of any threats
        
        Called periodically (every 5 minutes or manually via API)
        Returns count of alerts created
        """
        try:
            logger.info("[SECURITY MONITOR] Starting suspicious activity scan...")
            
            # Get all admin users
            admins = User.query.filter_by(role='admin', is_active=True).all()
            if not admins:
                logger.warning("[SECURITY MONITOR] No active admins to alert")
                return 0
            
            admin_ids = [admin.id for admin in admins]
            alerts_created = 0
            
            # Check all suspicious patterns
            detector = SuspiciousActivityDetector()
            alerts = detector.check_all_patterns()
            
            if alerts:
                logger.warning(f"[SECURITY MONITOR] ⚠️ Detected {len(alerts)} suspicious activity patterns")
                alerts_created = len(alerts)
            
            else:
                logger.info("[SECURITY MONITOR] ✓ No suspicious activities detected")
            
            # Check for critical account issues that need immediate attention
            critical_alerts = AdminSecurityMonitor._check_critical_issues(admin_ids)
            alerts_created += critical_alerts
            
            logger.info(f"[SECURITY MONITOR] Scan complete. {alerts_created} alerts created.")
            return alerts_created
            
        except Exception as e:
            logger.error(f"[SECURITY MONITOR] Error during security scan: {str(e)}", exc_info=True)
            return 0
    
    @staticmethod
    def _check_critical_issues(admin_ids):
        """Check for critical security issues requiring immediate admin attention"""
        alerts_count = 0
        
        try:
            # Check for very recent account lockouts (potential attack in progress)
            recent_lockouts = AuditLog.query.filter(
                and_(
                    AuditLog.event.in_(['user.account_locked', 'admin.account_locked']),
                    AuditLog.timestamp >= datetime.now(PH_TZ) - timedelta(minutes=5),
                    AuditLog.deleted_at.is_(None)
                )
            ).count()
            
            if recent_lockouts >= 3:
                # Alert all admins of potential coordinated attack
                title = "🚨 CRITICAL: Multiple Account Lockouts Detected"
                message = f"Multiple user accounts have been locked in the last 5 minutes. This may indicate a coordinated brute force attack. {recent_lockouts} lockouts detected."
                
                for admin_id in admin_ids:
                    NotificationManager.create_and_emit(
                        user_id=admin_id,
                        title=title,
                        message=message,
                        notification_type='security_alert',
                        link='/admin/audit-logs'
                    )
                
                alerts_count += 1
            
            # Check for suspicious password reset patterns
            recent_resets = AuditLog.query.filter(
                and_(
                    AuditLog.event.in_(['user.password_reset_success']),
                    AuditLog.timestamp >= datetime.now(PH_TZ) - timedelta(minutes=30),
                    AuditLog.deleted_at.is_(None)
                )
            ).count()
            
            if recent_resets >= 10:
                # Alert if many password resets happening rapidly
                title = "⚠️ Unusual Password Reset Activity"
                message = f"Unusually high number of password resets detected ({recent_resets}) in the last 30 minutes."
                
                for admin_id in admin_ids:
                    NotificationManager.create_and_emit(
                        user_id=admin_id,
                        title=title,
                        message=message,
                        notification_type='security_alert',
                        link='/admin/audit-logs'
                    )
                
                alerts_count += 1
            
        except Exception as e:
            logger.error(f"[SECURITY MONITOR] Error checking critical issues: {str(e)}")
        
        return alerts_count


def get_user_security_report(user_id):
    """Get comprehensive security report for a user
    
    Used for admin review when assessing if a user account has been compromised
    
    Args:
        user_id: User ID to generate report for
        
    Returns:
        Dictionary with security metrics and risk assessment
    """
    try:
        user_activity = SuspiciousActivityDetector.get_user_activity_summary(user_id, days=30)
        
        # Get additional context
        user = User.query.get(user_id)
        if not user:
            return {'error': 'User not found'}
        
        # Get recent audit logs
        recent_logs = AuditLog.query.filter(
            and_(
                AuditLog.actor_id == user_id,
                AuditLog.timestamp >= datetime.now(PH_TZ) - timedelta(days=30),
                AuditLog.deleted_at.is_(None)
            )
        ).order_by(AuditLog.timestamp.desc()).limit(20).all()
        
        return {
            'user_id': user_id,
            'user_email': user.email,
            'user_name': f"{user.first_name} {user.last_name}",
            'account_active': user.is_active,
            'account_locked': user.lockout_until and user.lockout_until > datetime.now(PH_TZ),
            '2fa_enabled': user.is_2fa_enabled,
            'activity_summary': user_activity,
            'recent_events': [
                {
                    'event': log.event,
                    'timestamp': log.timestamp.isoformat(),
                    'details': log.details,
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent
                }
                for log in recent_logs
            ],
            'risk_assessment': 'HIGH' if user_activity['risk_score'] > 70 else (
                'MEDIUM' if user_activity['risk_score'] > 40 else 'LOW'
            )
        }
        
    except Exception as e:
        logger.error(f"Error generating security report for user {user_id}: {str(e)}")
        return {'error': str(e)}


# ====== SECURITY REPORT HELPERS ======
