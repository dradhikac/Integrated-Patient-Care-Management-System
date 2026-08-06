import secrets
import random
from functools import wraps
from flask import request, redirect, url_for, flash, abort
from flask_login import current_user
from app.extensions import db
from app.auth.models import LoginLog

def role_required(*roles):
    """
    Decorator to restrict access based on user roles.
    Example: @role_required('Admin', 'Receptionist')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role.name not in roles:
                flash(f'Access denied. Required role: {", ".join(roles)}', 'danger')
                return redirect(url_for('auth.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_login_activity(email_attempted, status, user=None, failure_reason=None):
    """
    Log every authentication attempt with IP address and User Agent.
    """
    ip_addr = request.remote_addr or request.headers.get('X-Forwarded-For', 'Unknown')
    user_agent = request.user_agent.string[:250] if request.user_agent else 'Unknown'
    
    log = LoginLog(
        user_id=user.id if user else None,
        email_attempted=email_attempted,
        ip_address=ip_addr,
        user_agent=user_agent,
        status=status,
        failure_reason=failure_reason
    )
    db.session.add(log)
    db.session.commit()


def generate_otp():
    """Generate 6-digit OTP code"""
    return f"{random.randint(100000, 999999)}"


def generate_reset_token():
    """Generate 64-character URL-safe token"""
    return secrets.token_urlsafe(32)
