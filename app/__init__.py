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
        from .admin.routes import admin_bp

        app.register_blueprint(main_bp)
        app.register_blueprint(staff_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(dispatch_bp)
        app.register_blueprint(payroll_bp)
        app.register_blueprint(admin_bp)

    # --- Custom CLI Commands ---
    from .models import User, Agency, UserRole # Import User, Agency and UserRole enum here

    @app.cli.command("create-super-admin")
    @click.argument("username")
    @click.argument("password")
    def create_super_admin(username, password):
        """Creates a new user with the Super-Admin role."""
        if User.query.filter_by(username=username).first():
            print(f"Error: User '{username}' already exists.")
            return
        
        new_user = User(username=username, role=UserRole.SUPER_ADMIN.value)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        print(f"Success! Super-Admin user '{username}' was created.")

    @app.cli.command("create-role")
    @click.argument("role_name")
    def create_role(role_name):
        """Creates a new role."""
        if role_name not in [role.value for role in UserRole]:
            print(f"Error: Role '{role_name}' is not valid. Valid roles: {[role.value for role in UserRole]}")
            return
        
        print(f"Success! Role '{role_name}' is already available in the system.")

    @app.cli.command("promote-user")
    @click.argument("username")
    @click.argument("role_name")
    def promote_user(username, role_name):
        """Promotes a user to a specific role."""
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            return
        
        if role_name not in [role.value for role in UserRole]:
            print(f"Error: Role '{role_name}' is not valid. Valid roles: {[role.value for role in UserRole]}")
            return
        
        user.role = role_name
        db.session.commit()
        print(f"Success! User '{username}' was promoted to '{role_name}'.")

    @app.cli.command("check-users")
    def check_users():
        """Check and display all users with their roles and agencies."""
        print("=== USERS ===")
        users = User.query.all()
        for user in users:
            print(f"ID: {user.id}, Username: {user.username}, Role: {user.role}, Agency: {user.agency.name if user.agency else 'None'}")
        
        print("\n=== AGENCIES ===")
        agencies = Agency.query.all()
        for agency in agencies:
            print(f"ID: {agency.id}, Name: {agency.name}")
        
        print("\n=== AVAILABLE ROLES ===")
        for role in UserRole:
            print(f"Role: {role.value}")

    @app.cli.command("fix-webdev")
    def fix_webdev():
        """Fix WebDev user to have correct role and no agency association."""
        # Find WebDev user
        webdev_user = User.query.filter_by(username='WebDev').first()
        if not webdev_user:
            print("WebDev user not found!")
            return
        
        # Fix WebDev user
        webdev_user.role = UserRole.WEBDEV.value
        webdev_user.agency_id = None  # WebDev should not be associated with any specific agency
        db.session.commit()
        
        print(f"Fixed WebDev user: role={webdev_user.role}, agency_id={webdev_user.agency_id}")

    @app.cli.command("fix-user-agency")
    @click.argument("username")
    @click.argument("agency_name")
    def fix_user_agency(username, agency_name):
        """Fix a user's agency association."""
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            return
        
        agency = Agency.query.filter_by(name=agency_name).first()
        if not agency:
            print(f"Error: Agency '{agency_name}' not found.")
            return
        
        # Don't change WebDev users
        if user.role == UserRole.WEBDEV.value:
            print(f"Warning: User '{username}' is WebDev and should not be associated with any agency.")
            return
        
        user.agency_id = agency.id
        db.session.commit()
        print(f"Fixed user '{username}': agency_id={user.agency_id} (Agency: {agency.name})")

    @app.cli.command("list-users")
    def list_users():
        """Lists all users with their roles."""
        users = User.query.all()
        print("📊 Users:")
        for user in users:
            role_name = user.role_name if user.role else "No role"
            print(f"  - {user.username}: {role_name}")

    @app.cli.command("list-roles")
    def list_roles():
        """Lists all roles."""
        print("📊 Available Roles:")
        for role in UserRole:
            print(f"  - {role.value}")

    @app.cli.command("link-user-agency")
    @click.argument("username")
    @click.argument("agency_name")
    def link_user_agency(username, agency_name):
        """Links a user to an agency."""
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"Error: User '{username}' not found.")
            return
        
        agency = Agency.query.filter_by(name=agency_name).first()
        if not agency:
            print(f"Error: Agency '{agency_name}' not found.")
            return
        
        user.agency_id = agency.id
        db.session.commit()
        print(f"Success! User '{username}' linked to agency '{agency_name}'.")

    @app.cli.command("list-agencies")
    def list_agencies():
        """Lists all agencies."""
        agencies = Agency.query.all()
        print("📊 Agencies:")
        for agency in agencies:
            print(f"  - {agency.id}: {agency.name}")

    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("password")
    @click.argument("role_name")
    def create_user(username, password, role_name):
        """Creates a new user with specified role."""
        if User.query.filter_by(username=username).first():
            print(f"Error: User '{username}' already exists.")
            return
        
        # Validate role
        if role_name not in [role.value for role in UserRole]:
            print(f"Error: Role '{role_name}' is not valid. Valid roles: {[role.value for role in UserRole]}")
            return
        
        # Get or create default agency for non-WebDev users
        agency = None
        if role_name != UserRole.WEBDEV.value:
            agency = Agency.query.filter_by(name='Bangkok Agency').first()
            if not agency:
                agency = Agency(name='Bangkok Agency')
                db.session.add(agency)
                db.session.commit()
                print(f"Agency 'Bangkok Agency' created.")
        
        new_user = User(username=username, role=role_name, agency_id=agency.id if agency else None)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        print(f"Success! User '{username}' with role '{role_name}' was created.")

    @app.cli.command("create-agency")
    @click.argument("agency_name")
    def create_agency(agency_name):
        """Creates a new agency."""
        if Agency.query.filter_by(name=agency_name).first():
            print(f"Error: Agency '{agency_name}' already exists.")
            return
        
        new_agency = Agency(name=agency_name)
        db.session.add(new_agency)
        db.session.commit()
        print(f"Success! Agency '{agency_name}' was created.")

    @app.cli.command("rename-agency")
    @click.argument("old_name")
    @click.argument("new_name")
    def rename_agency(old_name, new_name):
        """Renames an agency."""
        agency = Agency.query.filter_by(name=old_name).first()
        if not agency:
            print(f"Error: Agency '{old_name}' not found.")
            return
        
        if Agency.query.filter_by(name=new_name).first():
            print(f"Error: Agency '{new_name}' already exists.")
            return
        
        agency.name = new_name
        db.session.commit()
        print(f"Success! Agency '{old_name}' renamed to '{new_name}'.")

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))