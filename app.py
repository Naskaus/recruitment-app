from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from datetime import datetime, date, time as dt_time, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask import Response
from weasyprint import HTML

# --- App Initialization ---
app = Flask(__name__)

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

app.config['SECRET_KEY'] = 'a-very-secret-and-hard-to-guess-key' # Replace with a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "recruitment.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Database Setup ---
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login' # Redirect to this route if user is not logged in
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'Super-Admin':
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

# --- Hardcoded Data (for now) ---
ADMIN_LIST = ["Admin 1", "Mama Rose", "Mama Joy", "Khun Somchai"]
VENUE_LIST = ["Red Dragon", "Mandarin", "Shark"]
ROLE_LIST = ["Dancer", "Hostess"]
STATUS_LIST = ["Active", "Working", "Quiet"] # NEW
CONTRACT_TYPES = {"1jour": 1, "10jours": 10, "1mois": 30}
DRINK_STAFF_COMMISSION = 100
DRINK_BAR_PRICE = 120

# Ensure an 'uploads' directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# =========================
# Models
# =========================

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(80), nullable=False, default='Admin') # e.g., 'Admin', 'Super-Admin'

    managed_assignments = db.relationship('Assignment', foreign_keys='Assignment.managed_by_user_id', back_populates='manager')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class StaffProfile(db.Model):
    __tablename__ = "staff_profile"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    nickname = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(20))
    instagram = db.Column(db.String(80))
    facebook = db.Column(db.String(80))
    line_id = db.Column(db.String(80))
    dob = db.Column(db.Date, nullable=False)
    height = db.Column(db.Integer)
    weight = db.Column(db.Float)
    status = db.Column(db.String(50), nullable=False, default='Active')
    photo_url = db.Column(db.String(200), default='/static/images/default_avatar.png')
    preferred_position = db.Column(db.String(50), nullable=True) 
    notes = db.Column(db.Text, nullable=True) # NEW FIELD FOR NOTES
    current_venue = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('Assignment', backref='staff', lazy=True)

    @property
    def age(self):
        if not self.dob:
            return None
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))



class Assignment(db.Model):
    __tablename__ = 'assignment'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff_profile.id'), nullable=True)
    managed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    archived_staff_name = db.Column(db.String(100), nullable=True)
    archived_staff_photo = db.Column(db.String(200), nullable=True)

    venue = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(50), nullable=False, server_default='Dancer')
    contract_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    base_salary = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='ongoing')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    manager = db.relationship('User', back_populates='managed_assignments')

    performance_records = db.relationship(
        'PerformanceRecord',
        backref='assignment',
        lazy=True,
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id, "staff_id": self.staff_id, "venue": self.venue,
            "role": self.role,
            "contract_type": self.contract_type, "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(), "base_salary": self.base_salary,
            "status": self.status,
        }

class PerformanceRecord(db.Model):
    __tablename__ = 'performance_record'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    record_date = db.Column(db.Date, nullable=False, default=date.today)
    arrival_time = db.Column(db.Time, nullable=True)
    departure_time = db.Column(db.Time, nullable=True)
    drinks_sold = db.Column(db.Integer, default=0)
    special_commissions = db.Column(db.Float, default=0.0)
    bonus = db.Column(db.Float, default=0.0)
    malus = db.Column(db.Float, default=0.0)
    lateness_penalty = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('assignment_id', 'record_date', name='uq_assignment_date'),)

    def to_dict(self):
        return {
            "id": self.id, "assignment_id": self.assignment_id, "record_date": self.record_date.isoformat(),
            "arrival_time": self.arrival_time.strftime('%H:%M') if self.arrival_time else None,
            "departure_time": self.departure_time.strftime('%H:%M') if self.departure_time else None,
            "drinks_sold": self.drinks_sold, "special_commissions": self.special_commissions,
            "bonus": self.bonus, "malus": self.malus, "lateness_penalty": self.lateness_penalty,
        }

# --- Login Manager Setup ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helper Functions ---
def compute_end_date(start_date: date, contract_type: str) -> date:
    days = CONTRACT_TYPES.get(contract_type)
    if not days:
        raise ValueError("Invalid contract_type")
    return start_date + timedelta(days=days - 1)

def calc_lateness_penalty(arrival_time):
    if not arrival_time:
        return 0
    cutoff = dt_time(19, 30)
    if arrival_time <= cutoff:
        return 0
    minutes = (datetime.combine(date.today(), arrival_time) - datetime.combine(date.today(), cutoff)).seconds // 60
    return minutes * 5

# =========================
# Auth Routes
# =========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('staff_list'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
        
        login_user(user, remember=remember)
        return redirect(url_for('staff_list'))
        
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/users', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_users():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        if not username or not password or not role:
            flash('All fields are required.', 'danger')
            return redirect(url_for('manage_users'))

        if role not in ['Admin', 'Super-Admin']:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('manage_users'))
            
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash(f'Username "{username}" already exists.', 'danger')
            return redirect(url_for('manage_users'))

        new_user = User(username=username, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'User "{username}" created successfully.', 'success')
        return redirect(url_for('manage_users'))

    all_users = User.query.order_by(User.id).all()
    return render_template('users.html', users=all_users)

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash("You cannot delete your own account.", 'danger')
        return redirect(url_for('manage_users'))

    user_to_delete = User.query.get_or_404(user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash(f'User "{user_to_delete.username}" has been deleted.', 'success')
    return redirect(url_for('manage_users'))

# =========================
# Views
# =========================

@app.route('/')
@app.route('/staff')
@login_required
def staff_list():
    all_profiles = StaffProfile.query.order_by(StaffProfile.created_at.desc()).all()
    # MODIFIED: Pass statuses to the template
    return render_template('staff_list.html', profiles=all_profiles, statuses=STATUS_LIST)

@app.route('/dispatch')
@login_required
def dispatch_board():
    all_staff = StaffProfile.query.all()
    available_staff = [s for s in all_staff if not s.current_venue]
    dispatched_staff = {venue: [s for s in all_staff if s.current_venue == venue] for venue in VENUE_LIST}
    all_users = User.query.order_by(User.username).all()
    return render_template('dispatch.html', 
                           available_staff=available_staff, 
                           dispatched_staff=dispatched_staff, 
                           venues=VENUE_LIST, 
                           roles=ROLE_LIST, 
                           users=all_users,
                           statuses=STATUS_LIST) # Pass the status list to the template

@app.route('/payroll')
@login_required
def payroll_page_new():
    selected_venue = request.args.get('venue')
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status')
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    # NEW: Get date strings from request arguments
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    q = Assignment.query.options(
        db.joinedload(Assignment.staff), 
        db.joinedload(Assignment.manager), 
        db.subqueryload(Assignment.performance_records)
    )

    # --- Apply filters ---
    if selected_venue:
        q = q.filter(Assignment.venue == selected_venue)
    
    if selected_contract_type:
        q = q.filter(Assignment.contract_type == selected_contract_type)
        
    if selected_status:
        q = q.filter(Assignment.status == selected_status)
    else:
        q = q.filter(Assignment.status.in_(['ongoing', 'archived']))

    if search_nickname:
        q = q.join(StaffProfile).filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))
    
    if selected_manager_id:
        q = q.filter(Assignment.managed_by_user_id == selected_manager_id)

    # NEW: Date range filtering logic
    start_date, end_date = None, None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            # Filter contracts that end on or after the start date of our range
            q = q.filter(Assignment.end_date >= start_date)
        except ValueError:
            flash(f'Invalid start date format: {start_date_str}. Please use YYYY-MM-DD.', 'danger')

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            # Filter contracts that start on or before the end date of our range
            q = q.filter(Assignment.start_date <= end_date)
        except ValueError:
            flash(f'Invalid end date format: {end_date_str}. Please use YYYY-MM-DD.', 'danger')
    
    status_order = db.case((Assignment.status == 'ongoing', 1), (Assignment.status == 'archived', 2), else_=3).label("status_order")
    all_assignments = q.order_by(status_order, Assignment.start_date.asc()).all()
    
    rows = []
    for a in all_assignments:
        contract_stats = {
            "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0
        }
        original_duration = CONTRACT_TYPES.get(a.contract_type, 1)
        base_daily_salary = (a.base_salary / original_duration) if original_duration > 0 else 0

        for record in a.performance_records:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
            daily_profit = bar_revenue - daily_salary
            
            contract_stats["drinks"] += record.drinks_sold or 0
            contract_stats["special_comm"] += record.special_commissions or 0
            contract_stats["salary"] += daily_salary
            contract_stats["commission"] += daily_commission
            contract_stats["profit"] += daily_profit

        rows.append({
            "assignment": a,
            "contract_days": (a.end_date - a.start_date).days + 1,
            "days_worked": len(a.performance_records),
            "original_duration": original_duration,
            "contract_stats": contract_stats
        })
        
    total_profit = sum(row['contract_stats']['profit'] for row in rows)
    total_days_worked = sum(row['days_worked'] for row in rows)

    summary_stats = {
        "total_profit": total_profit,
        "total_days_worked": total_days_worked
    }

    all_managers = User.query.order_by(User.username).all()

    filter_data = {
        "venues": VENUE_LIST,
        "contract_types": CONTRACT_TYPES.keys(),
        "statuses": ['ongoing', 'archived'],
        "managers": all_managers,
        "selected_venue": selected_venue,
        "selected_contract_type": selected_contract_type,
        "selected_status": selected_status,
        "search_nickname": search_nickname,
        "selected_manager_id": selected_manager_id,
        # NEW: Pass selected dates back to the template
        "selected_start_date": start_date_str,
        "selected_end_date": end_date_str
    }

    return render_template('payroll.html', assignments=rows, filters=filter_data, summary=summary_stats)
@app.route('/profile/new', methods=['GET'])
@login_required
def new_profile_form():
    current_year = date.today().year
    years = range(current_year - 18, current_year - 60, -1)
    months = range(1, 13)
    days = range(1, 32)
    
    # DIAGNOSTIC CODE - TEMPORARY
    try:
        from flask import current_app
        import os
        template_folder = current_app.template_folder
        absolute_template_path = os.path.abspath(template_folder)
        profile_form_path = os.path.join(absolute_template_path, 'profile_form.html')
        
        print("=" * 80)
        print("🔍 FLASK TEMPLATE DIAGNOSTIC - NEW PROFILE FORM")
        print("=" * 80)
        print(f"Template folder: {absolute_template_path}")
        print(f"Profile form path: {profile_form_path}")
        print(f"File exists: {os.path.exists(profile_form_path)}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"App instance folder: {current_app.instance_path}")
        print("=" * 80)
        
        # Force flush to ensure output appears
        import sys
        sys.stdout.flush()
        
    except Exception as e:
        print(f"🚨 DIAGNOSTIC ERROR: {e}")
        import sys
        sys.stdout.flush()
    
    return render_template('profile_form.html', years=years, months=months, days=days, admins=ADMIN_LIST, edit_mode=False)

@app.route('/profile/<int:profile_id>')
@login_required
def profile_detail(profile_id):
    profile = StaffProfile.query.options(
        db.joinedload(StaffProfile.assignments).subqueryload(Assignment.performance_records)
    ).get_or_404(profile_id)

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date, end_date = None, None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    all_assignments = sorted(profile.assignments, key=lambda a: a.start_date, reverse=True)
    
    if start_date or end_date:
        filtered_assignments = []
        for a in all_assignments:
            contract_starts_before_range_ends = not end_date or a.start_date <= end_date
            contract_ends_after_range_starts = not start_date or a.end_date >= start_date
            if contract_starts_before_range_ends and contract_ends_after_range_starts:
                filtered_assignments.append(a)
        assignments_to_process = filtered_assignments
    else:
        assignments_to_process = all_assignments

    total_days_worked = 0
    total_drinks_sold = 0
    total_special_comm = 0
    total_salary_paid = 0
    total_commission_paid = 0
    total_bar_profit = 0

    for assignment in assignments_to_process:
        assignment.contract_stats = {
            "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0
        }
        original_duration = CONTRACT_TYPES.get(assignment.contract_type, 1)
        base_daily_salary = (assignment.base_salary / original_duration) if original_duration > 0 else 0

        records_to_process = assignment.performance_records
        if start_date or end_date:
            records_to_process = [
                r for r in assignment.performance_records 
                if (not start_date or r.record_date >= start_date) and \
                   (not end_date or r.record_date <= end_date)
            ]

        for record in records_to_process:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
            daily_profit = bar_revenue - daily_salary
            
            assignment.contract_stats["drinks"] += record.drinks_sold or 0
            assignment.contract_stats["special_comm"] += record.special_commissions or 0
            assignment.contract_stats["salary"] += daily_salary
            assignment.contract_stats["commission"] += daily_commission
            assignment.contract_stats["profit"] += daily_profit
        
        total_days_worked += len(records_to_process)
        total_drinks_sold += assignment.contract_stats["drinks"]
        total_special_comm += assignment.contract_stats["special_comm"]
        total_salary_paid += assignment.contract_stats["salary"]
        total_commission_paid += assignment.contract_stats["commission"]
        total_bar_profit += assignment.contract_stats["profit"]

    history_stats = {
        "total_days_worked": total_days_worked,
        "total_drinks_sold": total_drinks_sold,
        "total_special_comm": total_special_comm,
        "total_salary_paid": total_salary_paid,
        "total_commission_paid": total_commission_paid,
        "total_bar_profit": total_bar_profit
    }
    
    return render_template(
        'profile_detail.html', 
        profile=profile,
        assignments=assignments_to_process,
        history_stats=history_stats,
        filter_start_date=start_date,
        filter_end_date=end_date
    )
@app.route('/profile/<int:profile_id>/edit', methods=['GET'])
@login_required
def edit_profile_form(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    current_year = date.today().year
    years = range(current_year - 18, current_year - 60, -1)
    months = range(1, 13)
    days = range(1, 32)
    
    # DIAGNOSTIC CODE - TEMPORARY
    try:
        from flask import current_app
        import os
        template_folder = current_app.template_folder
        absolute_template_path = os.path.abspath(template_folder)
        profile_form_path = os.path.join(absolute_template_path, 'profile_form.html')
        
        print("=" * 80)
        print("🔍 FLASK TEMPLATE DIAGNOSTIC - EDIT PROFILE FORM")
        print("=" * 80)
        print(f"Template folder: {absolute_template_path}")
        print(f"Profile form path: {profile_form_path}")
        print(f"File exists: {os.path.exists(profile_form_path)}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"App instance folder: {current_app.instance_path}")
        print("=" * 80)
        
        # Force flush to ensure output appears
        import sys
        sys.stdout.flush()
        
    except Exception as e:
        print(f"🚨 DIAGNOSTIC ERROR: {e}")
        import sys
        sys.stdout.flush()
    
    return render_template('profile_form.html', profile=profile, years=years, months=months, days=days, admins=ADMIN_LIST, edit_mode=True)

# =========================
# Profiles API
# =========================

@app.route('/api/profile', methods=['POST'])
@login_required
def create_profile():
    data = request.form
    if not data.get('nickname'):
        return jsonify({'status': 'error', 'message': 'Nickname is a required field.'}), 400
    try:
        dob_date = date(int(data.get('dob_year')), int(data.get('dob_month')), int(data.get('dob_day')))
    except Exception:
        return jsonify({'status': 'error', 'message': 'A valid Date of Birth is required.'}), 400
    photo_url = '/static/images/default_avatar.png'
    if 'photo' in request.files and request.files['photo'].filename != '':
        photo = request.files['photo']
        filename = secure_filename(photo.filename)
        unique_filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        photo.save(save_path)
        photo_url = f'/uploads/{unique_filename}'
    new_profile = StaffProfile(
        nickname=data.get('nickname'), dob=dob_date, first_name=data.get('first_name'),
        last_name=data.get('last_name'), phone=data.get('phone'), instagram=data.get('instagram'),
        facebook=data.get('facebook'), line_id=data.get('line_id'), height=data.get('height') or None,
        weight=data.get('weight') or None, photo_url=photo_url, 
        preferred_position=data.get('preferred_position'),
        notes=data.get('notes') # NEW: Save the notes
    )
    db.session.add(new_profile)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile created successfully!'}), 201

@app.route('/api/profile/<int:profile_id>', methods=['POST'])
@login_required
def update_profile(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    data = request.form
    if not data.get('nickname'):
        return jsonify({'status': 'error', 'message': 'Nickname is a required field.'}), 400
    try:
        dob_date = date(int(data.get('dob_year')), int(data.get('dob_month')), int(data.get('dob_day')))
    except Exception:
        return jsonify({'status': 'error', 'message': 'A valid Date of Birth is required.'}), 400
    if 'photo' in request.files and request.files['photo'].filename != '':
        photo = request.files['photo']
        filename = secure_filename(photo.filename)
        unique_filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        photo.save(save_path)
        profile.photo_url = f'/uploads/{unique_filename}'
    profile.nickname = data.get('nickname')
    profile.dob = dob_date
    profile.first_name = data.get('first_name')
    profile.last_name = data.get('last_name')
    profile.phone = data.get('phone')
    profile.instagram = data.get('instagram')
    profile.facebook = data.get('facebook')
    profile.line_id = data.get('line_id')
    profile.height = data.get('height') or None
    profile.weight = data.get('weight') or None
    profile.preferred_position = data.get('preferred_position')
    profile.notes = data.get('notes') # NEW: Save the notes
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile updated successfully!'}), 200

@app.route('/api/profile/<int:profile_id>/delete', methods=['POST'])
@login_required
def delete_profile(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)

    for assignment in list(profile.assignments):
        if assignment.status == 'archived':
            assignment.archived_staff_name = profile.nickname
            assignment.archived_staff_photo = profile.photo_url
            assignment.staff_id = None
        else:
            db.session.delete(assignment)
    
    if profile.photo_url and 'default_avatar' not in profile.photo_url:
        try:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(profile.photo_url))
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception as e:
            print(f"Error deleting photo {profile.photo_url}: {e}")

    db.session.delete(profile)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': 'Profile and associated ongoing contracts deleted successfully.'})


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =========================
# Staff Status API (NEW)
# =========================

@app.route('/api/profile/<int:profile_id>/status', methods=['POST'])
@login_required
def update_staff_status(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    data = request.get_json()
    new_status = data.get('status')

    if not new_status or new_status not in STATUS_LIST:
        return jsonify({'status': 'error', 'message': 'Invalid status provided.'}), 400

    profile.status = new_status
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': f'Status for {profile.nickname} updated to {new_status}.'})

# =========================
# Form Data API (NEW)
# =========================

@app.route('/api/assignment/form-data')
@login_required
def get_assignment_form_data():
    """Provides necessary data to populate the assignment form dynamically."""
    try:
        all_users = User.query.order_by(User.username).all()
        managers = [{"id": user.id, "username": user.username} for user in all_users]
        
        return jsonify({
            "status": "success",
            "roles": ROLE_LIST,
            "managers": managers
        })
    except Exception as e:
        # Log the exception e if you have a logger configured
        return jsonify({"status": "error", "message": "Could not retrieve form data."}), 500

# =========================
# Assignment API
# =========================

@app.route('/api/assignment', methods=['POST'])
@login_required
def create_assignment():
    data = request.get_json() or {}
    try:
        staff_id = int(data.get('staff_id'))
        venue = data.get('venue')
        role = data.get('role')
        contract_type = data.get('contract_type')
        start_date = datetime.fromisoformat(data.get('start_date')).date()
        base_salary = float(data.get('base_salary', 0))
        managed_by_user_id = int(data.get('managed_by_user_id'))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid payload. Check data types."}), 400
    
    if role not in ROLE_LIST: return jsonify({"status": "error", "message": f"Invalid role. Must be one of {ROLE_LIST}"}), 400
    if venue not in VENUE_LIST: return jsonify({"status": "error", "message": "Invalid venue."}), 400
    if contract_type not in CONTRACT_TYPES: return jsonify({"status": "error", "message": "Invalid contract_type."}), 400
    
    staff = StaffProfile.query.get(staff_id)
    if not staff: return jsonify({"status": "error", "message": "Staff not found."}), 404

    manager = User.query.get(managed_by_user_id)
    if not manager: return jsonify({"status": "error", "message": "Manager not found."}), 404
    
    overlapping = Assignment.query.filter(Assignment.staff_id == staff_id, Assignment.status == 'ongoing', Assignment.start_date <= start_date, Assignment.end_date >= start_date).first()
    if overlapping: return jsonify({"status": "error", "message": "Staff already has an ongoing contract overlapping this start date."}), 409
    
    end_date = compute_end_date(start_date, contract_type)
    new_a = Assignment(
        staff_id=staff_id, 
        venue=venue, 
        role=role, 
        contract_type=contract_type, 
        start_date=start_date, 
        end_date=end_date, 
        base_salary=base_salary, 
        status='ongoing',
        managed_by_user_id=managed_by_user_id
    )
    db.session.add(new_a)
    
    # Update staff status and current venue
    staff.current_venue = venue
    staff.status = 'Working' # NEW: Automatically set status to 'Working'
    
    db.session.commit()
    return jsonify({"status": "success", "assignment": new_a.to_dict()}), 201

@app.route('/api/assignment/<int:assignment_id>/end', methods=['POST'])
@login_required
def end_assignment_now(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    if a.status != 'ongoing':
        return jsonify({"status": "error", "message": "Assignment is not ongoing."}), 400
    today = date.today()
    a.end_date = today if today >= a.start_date else a.start_date
    a.status = 'completed'
    db.session.commit()
    return jsonify({
        "status": "success", 
        "assignment": a.to_dict(),
        "contract_days": (a.end_date - a.start_date).days + 1
    }), 200

@app.route('/api/assignment/<int:assignment_id>', methods=['DELETE'])
@login_required
def delete_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    if a.staff:
        a.staff.current_venue = None
    db.session.delete(a)
    db.session.commit()
    return jsonify({"status": "success"}), 200

@app.route('/api/assignment/<int:assignment_id>/finalize', methods=['POST'])
@login_required
def finalize_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    data = request.get_json() or {}
    final_status = data.get('status')

    if a.status not in ['ongoing', 'completed']:
        return jsonify({"status": "error", "message": f"Assignment cannot be finalized from its current state ({a.status})."}), 400
    if final_status != 'archived':
        return jsonify({"status": "error", "message": "Invalid final status. Must be 'archived'."}), 400
    
    a.status = 'archived'
    if a.staff:
        a.staff.current_venue = None
        # NEW: Automatically set status back to 'Active'
        a.staff.status = 'Active' 
        
    db.session.commit()
    return jsonify({"status": "success", "message": f"Assignment finalized as {final_status}.", "assignment": a.to_dict()}), 200

# =========================
# Performance API
# =========================

def _get_or_create_daily_record(assignment_id: int, ymd: date) -> 'PerformanceRecord':
    rec = PerformanceRecord.query.filter_by(assignment_id=assignment_id, record_date=ymd).first()
    if rec: return rec
    rec = PerformanceRecord(assignment_id=assignment_id, record_date=ymd)
    db.session.add(rec)
    db.session.commit()
    return rec

@app.route('/api/performance/<int:assignment_id>/<string:ymd>', methods=['GET'])
@login_required
def get_performance(assignment_id, ymd):
    try:
        day = datetime.fromisoformat(ymd).date()
    except Exception:
        return jsonify({"status": "error", "message": "Invalid date."}), 400
    rec = PerformanceRecord.query.filter_by(assignment_id=assignment_id, record_date=day).first()
    if not rec:
        return jsonify({"status": "success", "record": None}), 200
    return jsonify({"status": "success", "record": rec.to_dict()}), 200

@app.route('/api/performance/<int:assignment_id>', methods=['GET'])
@login_required
def list_performance_for_assignment(assignment_id):
    a = Assignment.query.get(assignment_id)
    if not a:
        return jsonify({"status": "error", "message": "Assignment not found."}), 404
    records = PerformanceRecord.query.filter_by(assignment_id=assignment_id) \
                                     .order_by(PerformanceRecord.record_date.desc()).all()
    original_days = CONTRACT_TYPES.get(a.contract_type)
    return jsonify({
        "status": "success",
        "records": [r.to_dict() for r in records],
        "contract": {
            "start_date": a.start_date.isoformat(),
            "end_date": a.end_date.isoformat(),
            "base_salary": a.base_salary,
            "contract_days": (a.end_date - a.start_date).days + 1,
            "contract_type": a.contract_type,
            "original_days": original_days,
            "status": a.status
        }
    }), 200


@app.route('/api/performance', methods=['POST'])
@login_required
def upsert_performance():
    data = request.get_json() or {}
    try:
        assignment_id = int(data.get('assignment_id'))
        ymd = datetime.fromisoformat(data.get('record_date')).date()
    except Exception:
        return jsonify({"status": "error", "message": "Invalid assignment_id or record_date"}), 400
    a = Assignment.query.get(assignment_id)
    if not a or a.status != 'ongoing':
        return jsonify({"status": "error", "message": "Performance can only be added to ongoing assignments."}), 400
    if not (a.start_date <= ymd <= a.end_date):
        return jsonify({"status": "error", "message": "Date outside contract period."}), 400
    rec = _get_or_create_daily_record(assignment_id, ymd)
    def time_or_none(s):
        if not s: return None
        try: return dt_time.fromisoformat(s)
        except Exception: return None
    rec.arrival_time = time_or_none(data.get('arrival_time'))
    rec.departure_time = time_or_none(data.get('departure_time'))
    rec.drinks_sold = int(data.get('drinks_sold') or 0)
    rec.special_commissions = float(data.get('special_commissions') or 0.0)
    rec.bonus = float(data.get('bonus') or 0.0)
    rec.malus = float(data.get('malus') or 0.0)
    rec.lateness_penalty = float(calc_lateness_penalty(rec.arrival_time))
    db.session.commit()
    return jsonify({"status": "success", "record": rec.to_dict()}), 200
# =========================
# CLI Commands
# =========================
@app.cli.command("create-user")
def create_user():
    """Creates a new user."""
    import click
    username = click.prompt("Enter username")
    password = click.prompt("Enter password", hide_input=True, confirmation_prompt=True)
    role = click.prompt("Enter role (Admin, Super-Admin)", default="Super-Admin")
    
    user = User.query.filter_by(username=username).first()
    if user:
        click.echo("User already exists.")
        return
        
    new_user = User(username=username, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    click.echo(f"User {username} created successfully with role {role}.")

# THIS ENTIRE BLOCK WAS MOVED OUTSIDE of the create_user function
@app.route('/payroll/pdf')
@login_required
def payroll_pdf():
    # --- This filtering logic is an EXACT copy from payroll_page_new ---
    selected_venue = request.args.get('venue')
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status')
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    q = Assignment.query.options(
        db.joinedload(Assignment.staff), 
        db.joinedload(Assignment.manager), 
        db.subqueryload(Assignment.performance_records)
    )

    if selected_venue: q = q.filter(Assignment.venue == selected_venue)
    if selected_contract_type: q = q.filter(Assignment.contract_type == selected_contract_type)
    if selected_status: q = q.filter(Assignment.status == selected_status)
    else: q = q.filter(Assignment.status.in_(['ongoing', 'archived']))
    if search_nickname: q = q.join(StaffProfile).filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))
    if selected_manager_id: q = q.filter(Assignment.managed_by_user_id == selected_manager_id)

    start_date, end_date = None, None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        q = q.filter(Assignment.end_date >= start_date)
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        q = q.filter(Assignment.start_date <= end_date)

    status_order = db.case((Assignment.status == 'ongoing', 1), (Assignment.status == 'archived', 2), else_=3).label("status_order")
    all_assignments = q.order_by(status_order, Assignment.start_date.asc()).all()

    rows = []
    for a in all_assignments:
        # ... (Data processing logic remains the same)
        contract_stats = { "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0 }
        original_duration = CONTRACT_TYPES.get(a.contract_type, 1)
        base_daily_salary = (a.base_salary / original_duration) if original_duration > 0 else 0
        for record in a.performance_records:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
            daily_profit = bar_revenue - daily_salary
            contract_stats["drinks"] += record.drinks_sold or 0
            contract_stats["special_comm"] += record.special_commissions or 0
            contract_stats["salary"] += daily_salary
            contract_stats["commission"] += daily_commission
            contract_stats["profit"] += daily_profit
        rows.append({
            "assignment": a, "contract_days": (a.end_date - a.start_date).days + 1,
            "days_worked": len(a.performance_records), "original_duration": original_duration,
            "contract_stats": contract_stats
        })

    total_profit = sum(row['contract_stats']['profit'] for row in rows)
    total_days_worked = sum(row['days_worked'] for row in rows)
    summary_stats = { "total_profit": total_profit, "total_days_worked": total_days_worked }

    # MODIFIED: Get manager name for display and ensure all filters are included
    manager_name = None
    if selected_manager_id:
        manager = User.query.get(selected_manager_id)
        if manager:
            manager_name = manager.username

    filter_data = {
        "selected_venue": selected_venue, 
        "selected_contract_type": selected_contract_type,
        "selected_status": selected_status, 
        "search_nickname": search_nickname,
        "selected_manager_name": manager_name,
        "selected_start_date": start_date_str, 
        "selected_end_date": end_date_str
    }

    # --- PDF Generation ---
    html_for_pdf = render_template('payroll_pdf.html', 
                                  assignments=rows, 
                                  summary=summary_stats,
                                  filters=filter_data,
                                  report_date=date.today())

    pdf = HTML(string=html_for_pdf).write_pdf()

    return Response(pdf,
                   mimetype='application/pdf',
                   headers={'Content-Disposition': 'inline; filename=payroll_report.pdf'})
@app.route('/assignment/<int:assignment_id>/pdf')
@login_required
def assignment_pdf(assignment_id):
    # 1. Fetch the specific assignment
    assignment = Assignment.query.options(
        db.joinedload(Assignment.staff),
        db.joinedload(Assignment.manager),
        db.subqueryload(Assignment.performance_records)
    ).get_or_404(assignment_id)

    # 2. Calculate its stats (similar logic to the payroll page)
    contract_stats = { "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0 }
    original_duration = CONTRACT_TYPES.get(assignment.contract_type, 1)
    base_daily_salary = (assignment.base_salary / original_duration) if original_duration > 0 else 0

    for record in assignment.performance_records:
        daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
        daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
        bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
        daily_profit = bar_revenue - daily_salary
        
        contract_stats["drinks"] += record.drinks_sold or 0
        contract_stats["special_comm"] += record.special_commissions or 0
        contract_stats["salary"] += daily_salary
        contract_stats["commission"] += daily_commission
        contract_stats["profit"] += daily_profit

    # 3. Prepare data for the template in the same structure as the main PDF report
    rows = [{
        "assignment": assignment,
        "contract_days": (assignment.end_date - assignment.start_date).days + 1,
        "days_worked": len(assignment.performance_records),
        "original_duration": original_duration,
        "contract_stats": contract_stats
    }]
    
    summary_stats = {
        "total_profit": contract_stats["profit"],
        "total_days_worked": len(assignment.performance_records)
    }

    # 4. Render the PDF using the SAME template for a consistent look
    html_for_pdf = render_template('payroll_pdf.html',
                                  assignments=rows,
                                  summary=summary_stats,
                                  contract_stats=contract_stats, # NEW: Pass the full stats dictionary
                                  filters={}, # No filters needed for a single report
                                  report_date=date.today())

    pdf = HTML(string=html_for_pdf).write_pdf()
    
    # Use staff name in the filename for clarity
    staff_name = assignment.staff.nickname if assignment.staff else assignment.archived_staff_name
    filename = f"report_{staff_name}_{assignment.start_date.strftime('%Y-%m-%d')}.pdf"

    return Response(pdf,
                   mimetype='application/pdf',
                   headers={'Content-Disposition': f'inline; filename={filename}'})
@app.route('/profile/<int:profile_id>/pdf')
@login_required
def profile_pdf(profile_id):
    profile = StaffProfile.query.options(
        db.joinedload(StaffProfile.assignments).subqueryload(Assignment.performance_records)
    ).get_or_404(profile_id)

    # --- This logic is copied from profile_detail to ensure data consistency ---
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date, end_date = None, None
    if start_date_str: start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str: end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    all_assignments = sorted(profile.assignments, key=lambda a: a.start_date, reverse=True)
    
    assignments_to_process = all_assignments
    if start_date or end_date:
        assignments_to_process = [
            a for a in all_assignments 
            if (not end_date or a.start_date <= end_date) and (not start_date or a.end_date >= start_date)
        ]

    # Calculate history stats based on the filtered assignments
    total_days_worked, total_drinks_sold, total_special_comm, total_salary_paid, total_commission_paid, total_bar_profit = 0, 0, 0, 0, 0, 0
    for assignment in assignments_to_process:
        assignment.contract_stats = { "profit": 0 } # Simplified for this context
        original_duration = CONTRACT_TYPES.get(assignment.contract_type, 1)
        base_daily_salary = (assignment.base_salary / original_duration) if original_duration > 0 else 0
        records_to_process = [r for r in assignment.performance_records if (not start_date or r.record_date >= start_date) and (not end_date or r.record_date <= end_date)]
        
        assignment_profit = 0
        for record in records_to_process:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            daily_profit = (((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)) - daily_salary
            
            total_salary_paid += daily_salary
            total_commission_paid += daily_commission
            total_bar_profit += daily_profit
            total_drinks_sold += record.drinks_sold or 0
            total_special_comm += record.special_commissions or 0
            assignment_profit += daily_profit

        assignment.contract_stats["profit"] = assignment_profit
        total_days_worked += len(records_to_process)

    history_stats = {
        "total_days_worked": total_days_worked, "total_drinks_sold": total_drinks_sold,
        "total_special_comm": total_special_comm, "total_salary_paid": total_salary_paid,
        "total_commission_paid": total_commission_paid, "total_bar_profit": total_bar_profit
    }
    # --- End of copied logic ---

    # MODIFIED: Pass the direct URL of the photo
    photo_url = None
    if profile.photo_url and 'default_avatar' not in profile.photo_url:
        # Build the full URL that WeasyPrint can access
        photo_url = url_for('uploaded_file', filename=os.path.basename(profile.photo_url), _external=True)

    html_for_pdf = render_template('profile_pdf.html',
                                  profile=profile,
                                  photo_url=photo_url, # MODIFIED: Pass the full URL
                                  history_stats=history_stats,
                                  assignments=assignments_to_process,
                                  report_date=date.today())

    pdf = HTML(string=html_for_pdf).write_pdf()
    
    filename = f"profile_{profile.nickname}.pdf"
    return Response(pdf,
                   mimetype='application/pdf',
                   headers={'Content-Disposition': f'inline; filename={filename}'})