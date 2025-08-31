# app/main/routes.py
from flask import Blueprint, redirect, url_for
from flask_login import login_required
from app.decorators import admin_required, manager_required, super_admin_required, webdev_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
@admin_required
def index():
    # Redirige la page d'accueil vers la liste du staff
    return redirect(url_for('staff.staff_list'))
