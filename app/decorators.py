# app/decorators.py

from functools import wraps
from flask import abort
from flask_login import current_user
from app.models import UserRole

def admin_required(f):
    """Décorateur pour vérifier que l'utilisateur a au moins le rôle 'admin'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.ADMIN.value, UserRole.MANAGER.value, UserRole.SUPER_ADMIN.value, UserRole.WEBDEV.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    """Décorateur pour vérifier que l'utilisateur a au moins le rôle 'manager'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.MANAGER.value, UserRole.SUPER_ADMIN.value, UserRole.WEBDEV.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """Décorateur pour vérifier que l'utilisateur a au moins le rôle 'super_admin'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.SUPER_ADMIN.value, UserRole.WEBDEV.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def webdev_required(f):
    """Décorateur pour vérifier que l'utilisateur a le rôle 'webdev' ou 'super_admin'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.WEBDEV.value, UserRole.SUPER_ADMIN.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def user_management_required(f):
    """Décorateur pour vérifier que l'utilisateur a le rôle 'webdev' ou 'super_admin'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.WEBDEV.value, UserRole.SUPER_ADMIN.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def staff_management_required(f):
    """Décorateur pour vérifier que l'utilisateur a le rôle 'webdev', 'super_admin' ou 'manager'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.WEBDEV.value, UserRole.SUPER_ADMIN.value, UserRole.MANAGER.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def assignment_management_required(f):
    """Décorateur pour vérifier que l'utilisateur a le rôle 'webdev', 'super_admin', 'admin' ou 'manager'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.WEBDEV.value, UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, UserRole.MANAGER.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def dispatch_view_required(f):
    """Décorateur pour vérifier que l'utilisateur a le rôle 'webdev', 'super_admin', 'admin' ou 'manager'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.WEBDEV.value, UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, UserRole.MANAGER.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def payroll_view_required(f):
    """Décorateur pour vérifier que l'utilisateur a le rôle 'webdev', 'super_admin', 'admin' ou 'manager'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.WEBDEV.value, UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, UserRole.MANAGER.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def dispatch_edit_required(f):
    """Décorateur pour vérifier que l'utilisateur a le rôle 'webdev', 'super_admin', 'admin' ou 'manager'"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized
        if current_user.role not in [UserRole.WEBDEV.value, UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, UserRole.MANAGER.value]:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    """Décorateur flexible pour vérifier un rôle spécifique"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)  # Unauthorized
            if current_user.role != required_role:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator
