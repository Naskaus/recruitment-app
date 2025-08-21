# app/main/routes.py
from flask import Blueprint, redirect, url_for
from flask_login import login_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    # Redirige la page d'accueil vers la liste du staff
    return redirect(url_for('staff.staff_list'))
