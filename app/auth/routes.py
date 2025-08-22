# app/auth/routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User
from functools import wraps

# Imports for WTF-Forms
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired

# Blueprint Definition
auth_bp = Blueprint('auth', __name__, template_folder='../templates')

# --- Form Classes ---
class LoginForm(FlaskForm):
    """Login form."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Decorator for Super-Admins
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Super-Admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('staff.staff_list'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # This block now only runs if the form is POSTed and is valid (including CSRF token)
        user = User.query.filter_by(username=form.username.data).first()
        if not user or not user.check_password(form.password.data):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=True)
        return redirect(url_for('staff.staff_list'))
        
    return render_template('login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# CORRECTED: Function renamed from 'manage_users' to 'users'
@auth_bp.route('/users', methods=['GET', 'POST'])
@login_required
@super_admin_required
def users():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        if not username or not password or not role:
            flash('All fields are required.', 'danger')
            # CORRECTED: url_for target updated to 'auth.users'
            return redirect(url_for('auth.users'))
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash(f'Username "{username}" already exists.', 'danger')
            # CORRECTED: url_for target updated to 'auth.users'
            return redirect(url_for('auth.users'))
        new_user = User(username=username, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f'User "{username}" created successfully.', 'success')
        # CORRECTED: url_for target updated to 'auth.users'
        return redirect(url_for('auth.users'))

    all_users = User.query.order_by(User.id).all()
    return render_template('users.html', users=all_users)

@auth_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("You cannot delete your own account.", 'danger')
        # CORRECTED: url_for target updated to 'auth.users'
        return redirect(url_for('auth.users'))
    user_to_delete = User.query.get_or_404(user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'User "{user_to_delete.username}" has been deleted.', 'success')
    # CORRECTED: url_for target updated to 'auth.users'
    return redirect(url_for('auth.users'))