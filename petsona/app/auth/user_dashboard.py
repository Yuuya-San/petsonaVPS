from flask import render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from . import bp

@bp.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.role != 'user':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('user/dashboard.html')
