# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import os
import click # Import click for commands
from config import config_by_name

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = 'auth.login'
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

def create_app():
    # The config name is determined by the FLASK_ENV variable
    config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # --- Initializations ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # --- Blueprint Registration ---
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

    # --- Custom CLI Commands ---
    from .models import User # Import User model here

    @app.cli.command("create-super-admin")
    @click.argument("username")
    @click.argument("password")
    def create_super_admin(username, password):
        """Creates a new user with the Super-Admin role."""
        if User.query.filter_by(username=username).first():
            print(f"Error: User '{username}' already exists.")
            return
        
        new_user = User(username=username, role='Super-Admin')
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        print(f"Success! Super-Admin user '{username}' was created.")


    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))