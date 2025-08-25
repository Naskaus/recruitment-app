# app/auth/routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
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

# Decorator for Super-Admins and WebDev
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role_name not in ['Super-Admin', 'WebDev']:
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
        # Get the role object
        from app.models import Role
        role_obj = Role.query.filter_by(name=role).first()
        if not role_obj:
            flash(f'Role "{role}" not found.', 'danger')
            return redirect(url_for('auth.users'))
        
        # Super-Admin cannot create WebDev users
        if current_user.role_name == 'Super-Admin' and role_obj.name == 'WebDev':
            flash('Super-Admin cannot create WebDev users.', 'danger')
            return redirect(url_for('auth.users'))
        
        # Get current agency ID for association
        from flask import session
        if current_user.role_name == 'WebDev':
            agency_id = session.get('current_agency_id', current_user.agency_id)
            # For WebDev, ensure we have a valid agency_id for non-WebDev users
            if not agency_id and role_obj.name != 'WebDev':
                flash('Please select an agency before creating non-WebDev users.', 'danger')
                return redirect(url_for('auth.users'))
        else:
            agency_id = current_user.agency_id
        
        # Associate user with agency based on role
        if role_obj.name == 'WebDev':
            # WebDev users are not associated with any specific agency (can access all)
            new_user = User(username=username, role_id=role_obj.id, agency_id=None)
        else:
            # All other roles must be associated with the current agency
            new_user = User(username=username, role_id=role_obj.id, agency_id=agency_id)
        
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f'User "{username}" created successfully.', 'success')
        # CORRECTED: url_for target updated to 'auth.users'
        return redirect(url_for('auth.users'))

    # Get all roles for the form
    from app.models import Role
    # Super-Admin cannot create WebDev users
    if current_user.role_name == 'Super-Admin':
        all_roles = Role.query.filter(Role.name != 'WebDev').order_by(Role.name).all()
    else:
        # WebDev can create any role
        all_roles = Role.query.order_by(Role.name).all()
    
    # Get all users with their roles and agencies
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Super-Admin cannot see WebDev users
    if current_user.role_name == 'Super-Admin':
        all_users = User.query.options(
            db.joinedload(User.role),
            db.joinedload(User.agency)
        ).join(Role).filter(Role.name != 'WebDev').filter(User.agency_id == agency_id).order_by(User.id).all()
    else:
        # WebDev can see users from current agency + WebDev users
        all_users = User.query.options(
            db.joinedload(User.role),
            db.joinedload(User.agency)
        ).filter(
            db.or_(
                User.agency_id == agency_id,  # Users from current agency
                User.role_id == Role.query.filter_by(name='WebDev').first().id  # WebDev users
            )
        ).order_by(User.id).all()
    
    return render_template('users.html', users=all_users, roles=all_roles)

@auth_bp.route('/users/edit', methods=['POST'])
@login_required
@super_admin_required
def edit_user():
    user_id = request.form.get('user_id')
    username = request.form.get('username')
    role = request.form.get('role')
    password = request.form.get('password')
    
    if not user_id or not username or not role:
        flash('All fields are required.', 'danger')
        return redirect(url_for('auth.users'))
    
    user_to_edit = User.query.get_or_404(user_id)
    
    # Check if username already exists (excluding current user)
    existing_user = User.query.filter_by(username=username).filter(User.id != user_id).first()
    if existing_user:
        flash(f'Username "{username}" already exists.', 'danger')
        return redirect(url_for('auth.users'))
    
    # Get the role object
    from app.models import Role
    role_obj = Role.query.filter_by(name=role).first()
    if not role_obj:
        flash(f'Role "{role}" not found.', 'danger')
        return redirect(url_for('auth.users'))
    
    # Super-Admin cannot edit WebDev users
    if current_user.role_name == 'Super-Admin' and role_obj.name == 'WebDev':
        flash('Super-Admin cannot edit WebDev users.', 'danger')
        return redirect(url_for('auth.users'))
    
    # Get current agency ID for association
    from flask import session
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Update user
    user_to_edit.username = username
    user_to_edit.role_id = role_obj.id
    
    # Update agency association based on role
    if role_obj.name == 'WebDev':
        # WebDev users are not associated with any specific agency
        user_to_edit.agency_id = None
    else:
        # All other roles must be associated with the current agency
        user_to_edit.agency_id = agency_id
    
    # Update password if provided
    if password:
        user_to_edit.set_password(password)
    
    db.session.commit()
    flash(f'User "{username}" updated successfully.', 'success')
    return redirect(url_for('auth.users'))

@auth_bp.route('/auth/api/agencies')
@login_required
def get_agencies():
    """Get all agencies available to the current user."""
    from app.models import Agency
    from flask import session
    
    # For WebDev, show all agencies
    if current_user.role_name == 'WebDev':
        agencies = Agency.query.all()
        # Use session agency for WebDev if set, otherwise use first agency
        current_agency_id = session.get('current_agency_id', agencies[0].id if agencies else None)
    else:
        # For other users, only show their assigned agency
        agencies = [current_user.agency] if current_user.agency else []
        current_agency_id = current_user.agency_id
    
    return jsonify({
        'agencies': [{'id': agency.id, 'name': agency.name} for agency in agencies],
        'current_agency_id': current_agency_id
    })

@auth_bp.route('/auth/api/switch-agency', methods=['POST'])
@login_required
def switch_agency():
    # Only WebDev can switch agencies
    if current_user.role_name != 'WebDev':
        return jsonify({'message': 'Access denied. Only WebDev can switch agencies.'}), 403
    """Switch the current user's agency."""
    from app.models import Agency
    from flask import session
    
    data = request.get_json()
    agency_id = data.get('agency_id')
    
    if not agency_id:
        return jsonify({'message': 'Agency ID is required'}), 400
    
    # Check if user can access this agency
    if current_user.role_name == 'WebDev':
        # WebDev can access any agency
        agency = Agency.query.get(agency_id)
    else:
        # Other users can only access their assigned agency
        if current_user.agency_id != agency_id:
            return jsonify({'message': 'Access denied'}), 403
        agency = current_user.agency
    
    if not agency:
        return jsonify({'message': 'Agency not found'}), 404
    
    # Store the selected agency in session for WebDev users
    if current_user.role_name == 'WebDev':
        session['current_agency_id'] = agency_id
        session['current_agency_name'] = agency.name
    
    return jsonify({
        'message': 'Agency switched successfully',
        'agency_name': agency.name
    })

@auth_bp.route('/auth/api/contracts', methods=['POST'])
@login_required
@super_admin_required
def create_contract():
    """Create a new contract type."""
    data = request.get_json()
    
    # For now, just return success (we'll implement the database model later)
    return jsonify({
        'message': 'Contract created successfully',
        'contract': data
    })

@auth_bp.route('/contracts')
@login_required
@super_admin_required
def contracts():
    """Manage contracts page."""
    return render_template('contracts.html')

@auth_bp.route('/venues')
@login_required
@super_admin_required
def venues():
    """Manage venues page."""
    return render_template('venues.html')

@auth_bp.route('/profile-form-config')
@login_required
@super_admin_required
def profile_form_config():
    """Manage profile form configuration page."""
    from app.models import AgencyPosition, Agency
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        abort(403, "User not associated with an agency.")
    
    # Get current agency
    current_agency = Agency.query.get(agency_id)
    if not current_agency:
        abort(403, "Agency not found.")
    
    # Get positions for current agency
    positions = AgencyPosition.query.filter_by(agency_id=agency_id).order_by(AgencyPosition.name).all()
    
    return render_template('profile_form_config.html', 
                         current_agency=current_agency,
                         positions=positions)

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

# Venues API routes
@auth_bp.route('/auth/api/venues')
@login_required
@super_admin_required
def get_venues():
    """Get all venues for the current agency."""
    from app.models import Venue
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        return jsonify({'message': 'No agency assigned'}), 400
    
    venues = Venue.query.filter_by(agency_id=agency_id).all()
    return jsonify({
        'venues': [{
            'id': venue.id,
            'name': venue.name,
            'logo_url': venue.logo_url,
            'assignments_count': venue.assignments.count()
        } for venue in venues]
    })

@auth_bp.route('/auth/api/venues', methods=['POST'])
@login_required
@super_admin_required
def create_venue():
    """Create a new venue."""
    from app.models import Venue
    from flask import session
    import os
    from werkzeug.utils import secure_filename
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        return jsonify({'success': False, 'message': 'No agency assigned'}), 400
    
    name = request.form.get('name')
    if not name:
        return jsonify({'success': False, 'message': 'Venue name is required'}), 400
    
    # Handle logo upload
    logo_url = None
    if 'logo' in request.files:
        logo_file = request.files['logo']
        if logo_file and logo_file.filename:
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'venues')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save the file
            filename = secure_filename(logo_file.filename)
            filepath = os.path.join(upload_dir, filename)
            logo_file.save(filepath)
            logo_url = f'/static/uploads/venues/{filename}'
    
    # Check if venue with same name already exists in this agency
    existing_venue = Venue.query.filter_by(name=name, agency_id=agency_id).first()
    if existing_venue:
        return jsonify({'success': False, 'message': f'Venue "{name}" already exists in this agency'}), 400
    
    # Create new venue
    new_venue = Venue(name=name, logo_url=logo_url, agency_id=agency_id)
    db.session.add(new_venue)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Venue "{name}" created successfully',
        'venue': {
            'id': new_venue.id,
            'name': new_venue.name,
            'logo_url': new_venue.logo_url
        }
    })

@auth_bp.route('/auth/api/venues/<int:venue_id>', methods=['PUT'])
@login_required
@super_admin_required
def update_venue(venue_id):
    """Update an existing venue."""
    from app.models import Venue
    from flask import session
    import os
    from werkzeug.utils import secure_filename
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    venue = Venue.query.filter_by(id=venue_id, agency_id=agency_id).first()
    if not venue:
        return jsonify({'success': False, 'message': 'Venue not found'}), 404
    
    name = request.form.get('name')
    if not name:
        return jsonify({'success': False, 'message': 'Venue name is required'}), 400
    
    # Check if venue with same name already exists in this agency (excluding current venue)
    existing_venue = Venue.query.filter_by(name=name, agency_id=agency_id).filter(Venue.id != venue_id).first()
    if existing_venue:
        return jsonify({'success': False, 'message': f'Venue "{name}" already exists in this agency'}), 400
    
    # Handle logo upload
    if 'logo' in request.files:
        logo_file = request.files['logo']
        if logo_file and logo_file.filename:
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'venues')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save the file
            filename = secure_filename(logo_file.filename)
            filepath = os.path.join(upload_dir, filename)
            logo_file.save(filepath)
            venue.logo_url = f'/static/uploads/venues/{filename}'
    
    venue.name = name
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Venue "{name}" updated successfully',
        'venue': {
            'id': venue.id,
            'name': venue.name,
            'logo_url': venue.logo_url
        }
    })

@auth_bp.route('/auth/api/venues/<int:venue_id>', methods=['DELETE'])
@login_required
@super_admin_required
def delete_venue(venue_id):
    """Delete a venue."""
    from app.models import Venue, Assignment
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    venue = Venue.query.filter_by(id=venue_id, agency_id=agency_id).first()
    if not venue:
        return jsonify({'success': False, 'message': 'Venue not found'}), 404
    
    # Check if there are assignments linked to this venue
    linked_assignments = Assignment.query.filter_by(venue_id=venue_id).all()
    venue_name = venue.name
    
    # Keep assignments but set venue_id to NULL
    if linked_assignments:
        for assignment in linked_assignments:
            assignment.venue_id = None
        message = f'Venue "{venue_name}" deleted successfully. {len(linked_assignments)} assignments were kept but are now unassigned.'
    else:
        message = f'Venue "{venue_name}" deleted successfully'
    
    # Delete the venue
    db.session.delete(venue)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': message
    })

@auth_bp.route('/add-agency', methods=['GET', 'POST'])
@login_required
def add_agency():
    """Add a new agency - WebDev only."""
    if current_user.role_name != 'WebDev':
        abort(403, "Only WebDev users can add agencies.")
    
    if request.method == 'POST':
        agency_name = request.form.get('agency_name')
        if not agency_name:
            flash('Agency name is required.', 'danger')
            return redirect(url_for('auth.add_agency'))
        
        # Check if agency with same name already exists
        from app.models import Agency
        existing_agency = Agency.query.filter_by(name=agency_name).first()
        if existing_agency:
            flash(f'Agency "{agency_name}" already exists.', 'danger')
            return redirect(url_for('auth.add_agency'))
        
        # Create new agency
        new_agency = Agency(name=agency_name)
        db.session.add(new_agency)
        db.session.commit()
        
        flash(f'Agency "{agency_name}" created successfully.', 'success')
        return redirect(url_for('auth.add_agency'))
    
    return render_template('add_agency.html')

# Agency Positions API routes
@auth_bp.route('/auth/api/positions')
@login_required
@super_admin_required
def get_positions():
    """Get all positions for the current agency."""
    from app.models import AgencyPosition
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        return jsonify({'message': 'No agency assigned'}), 400
    
    positions = AgencyPosition.query.filter_by(agency_id=agency_id).order_by(AgencyPosition.name).all()
    return jsonify({
        'positions': [{
            'id': position.id,
            'name': position.name
        } for position in positions]
    })

@auth_bp.route('/auth/api/positions', methods=['POST'])
@login_required
@super_admin_required
def create_position():
    """Create a new position for the current agency."""
    from app.models import AgencyPosition
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        return jsonify({'success': False, 'message': 'No agency assigned'}), 400
    
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Position name is required'}), 400
    
    # Check if position with same name already exists in this agency
    existing_position = AgencyPosition.query.filter_by(name=name, agency_id=agency_id).first()
    if existing_position:
        return jsonify({'success': False, 'message': f'Position "{name}" already exists in this agency'}), 400
    
    # Create new position
    new_position = AgencyPosition(name=name, agency_id=agency_id)
    db.session.add(new_position)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Position "{name}" created successfully',
        'position': {
            'id': new_position.id,
            'name': new_position.name
        }
    })

@auth_bp.route('/auth/api/positions/<int:position_id>', methods=['PUT'])
@login_required
@super_admin_required
def update_position(position_id):
    """Update a position."""
    from app.models import AgencyPosition
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        return jsonify({'success': False, 'message': 'No agency assigned'}), 400
    
    position = AgencyPosition.query.filter_by(id=position_id, agency_id=agency_id).first()
    if not position:
        return jsonify({'success': False, 'message': 'Position not found'}), 404
    
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Position name is required'}), 400
    
    # Check if position with same name already exists in this agency (excluding current)
    existing_position = AgencyPosition.query.filter_by(name=name, agency_id=agency_id).filter(AgencyPosition.id != position_id).first()
    if existing_position:
        return jsonify({'success': False, 'message': f'Position "{name}" already exists in this agency'}), 400
    
    position.name = name
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Position updated successfully',
        'position': {
            'id': position.id,
            'name': position.name
        }
    })

@auth_bp.route('/auth/api/positions/<int:position_id>', methods=['DELETE'])
@login_required
@super_admin_required
def delete_position(position_id):
    """Delete a position."""
    from app.models import AgencyPosition
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        return jsonify({'success': False, 'message': 'No agency assigned'}), 400
    
    position = AgencyPosition.query.filter_by(id=position_id, agency_id=agency_id).first()
    if not position:
        return jsonify({'success': False, 'message': 'Position not found'}), 404
    
    position_name = position.name
    db.session.delete(position)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Position "{position_name}" deleted successfully'
    })

