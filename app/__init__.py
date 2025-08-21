# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

def create_app():
    app = Flask(__name__)

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    app.config['SECRET_KEY'] = 'a-very-secret-and-hard-to-guess-key'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, '..', 'uploads')
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'sslmode': 'require'}}
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "..", "recruitment.db")}'

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    with app.app_context():
        from .main.routes import main_bp
        from .staff.routes import staff_bp
        from .auth.routes import auth_bp
        from .dispatch.routes import dispatch_bp
        from .payroll.routes import payroll_bp

        app.register_blueprint(main_bp)
        app.register_blueprint(staff_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(dispatch_bp)
        app.register_blueprint(payroll_bp)

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))