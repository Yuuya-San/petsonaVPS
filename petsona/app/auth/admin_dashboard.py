from flask import render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from . import bp

@bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('admin_dashboard/admin_dashboard.html')
