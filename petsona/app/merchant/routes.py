from flask import render_template, flash, redirect, url_for
from flask_login import login_required, current_user # pyright: ignore[reportMissingImports]
from app.merchant import bp
from app.decorators import merchant_required

@bp.route('/dashboard')
@login_required
@merchant_required
def dashboard():
    if current_user.role != 'merchant':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.login'))

    return render_template('merchant/dashboard.html')
