from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from datetime import datetime, date, time as dt_time
from werkzeug.utils import secure_filename
import time

# --- App Initialization ---
app = Flask(__name__)

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "recruitment.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Database Setup ---
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Hardcoded Data (for now) ---
ADMIN_LIST = ["Admin 1", "Mama Rose", "Mama Joy", "Khun Somchai"]
VENUE_LIST = ["Red Dragon", "Mandarin", "Shark"]

# Ensure an 'uploads' directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Database Models ---
class StaffProfile(db.Model):
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
    admin_mama_name = db.Column(db.String(80))
    current_venue = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    performance_records = db.relationship('PerformanceRecord', backref='staff_profile', lazy=True, cascade="all, delete-orphan")

    @property
    def age(self):
        if not self.dob: return None
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

class PerformanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff_profile.id'), nullable=False)
    record_date = db.Column(db.Date, nullable=False, default=date.today)
    arrival_time = db.Column(db.Time, nullable=True)
    departure_time = db.Column(db.Time, nullable=True)
    drinks_sold = db.Column(db.Integer, default=0)
    special_commissions = db.Column(db.Float, default=0)
    daily_salary = db.Column(db.Float, default=800)
    other_deductions = db.Column(db.Float, default=0)
    lateness_penalty = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'staff_id': self.staff_id,
            'record_date': self.record_date.isoformat(),
            'arrival_time': self.arrival_time.strftime('%H:%M') if self.arrival_time else None,
            'departure_time': self.departure_time.strftime('%H:%M') if self.departure_time else None,
            'drinks_sold': self.drinks_sold,
            'special_commissions': self.special_commissions,
            'daily_salary': self.daily_salary,
            'other_deductions': self.other_deductions,
            'lateness_penalty': self.lateness_penalty,
        }

# --- Data Definitions ---
STATUS_LEVELS = [
    "Active", "On assignment", "Quiet (recent)", "Moderately active", 
    "On holiday", "Inactive (long time)"
]

# --- Routes ---

@app.route('/')
@app.route('/staff')
def staff_list():
    all_profiles = StaffProfile.query.order_by(StaffProfile.created_at.desc()).all()
    return render_template('staff_list.html', profiles=all_profiles, statuses=STATUS_LEVELS)

@app.route('/dispatch')
def dispatch_board():
    all_staff = StaffProfile.query.all()
    available_staff = [s for s in all_staff if not s.current_venue]
    dispatched_staff = {venue: [s for s in all_staff if s.current_venue == venue] for venue in VENUE_LIST}
    return render_template('dispatch.html',
                           available_staff=available_staff,
                           dispatched_staff=dispatched_staff,
                           venues=VENUE_LIST)

@app.route('/payroll')
def payroll_page():
    """Display staff on assignment for payroll entry."""
    today = date.today()
    assigned_staff = StaffProfile.query.filter(StaffProfile.current_venue.isnot(None)).all()
    
    for staff in assigned_staff:
        record = PerformanceRecord.query.filter_by(staff_id=staff.id, record_date=today).first()
        if record:
            staff.has_record_for_today = True
            staff.record_id_for_today = record.id
        else:
            staff.has_record_for_today = False
            staff.record_id_for_today = None
            
    return render_template('payroll.html', assigned_staff=assigned_staff, today=today)


@app.route('/profile/new', methods=['GET'])
def new_profile_form():
    current_year = date.today().year
    years = range(current_year - 18, current_year - 60, -1)
    months = range(1, 13)
    days = range(1, 32)
    return render_template('profile_form.html', years=years, months=months, days=days, admins=ADMIN_LIST, edit_mode=False)

@app.route('/profile/<int:profile_id>')
def profile_detail(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    return render_template('profile_detail.html', profile=profile)

@app.route('/profile/<int:profile_id>/edit', methods=['GET'])
def edit_profile_form(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    current_year = date.today().year
    years = range(current_year - 18, current_year - 60, -1)
    months = range(1, 13)
    days = range(1, 32)
    return render_template('profile_form.html', profile=profile, years=years, months=months, days=days, admins=ADMIN_LIST, edit_mode=True)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- API Endpoints ---

@app.route('/api/profile', methods=['POST'])
def create_profile():
    data = request.form
    if not data.get('nickname'):
        return jsonify({'status': 'error', 'message': 'Nickname is a required field.'}), 400
    try:
        year = int(data.get('dob_year'))
        month = int(data.get('dob_month'))
        day = int(data.get('dob_day'))
        dob_date = date(year, month, day)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'A valid Date of Birth is required.'}), 400

    photo_url = '/static/images/default_avatar.png'
    if 'photo' in request.files:
        photo = request.files['photo']
        if photo.filename != '':
            filename = secure_filename(photo.filename)
            unique_filename = f"{int(time.time())}_{filename}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            photo.save(save_path)
            photo_url = f'/uploads/{unique_filename}'
    
    new_profile = StaffProfile(
        nickname=data.get('nickname'), dob=dob_date, first_name=data.get('first_name'),
        last_name=data.get('last_name'), phone=data.get('phone'), instagram=data.get('instagram'),
        facebook=data.get('facebook'), line_id=data.get('line_id'), height=data.get('height') or None,
        weight=data.get('weight') or None, photo_url=photo_url, admin_mama_name=data.get('admin_mama_name')
    )

    db.session.add(new_profile)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile created successfully!'}), 201

@app.route('/api/profile/<int:profile_id>', methods=['POST'])
def update_profile(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    data = request.form
    
    if not data.get('nickname'):
        return jsonify({'status': 'error', 'message': 'Nickname is a required field.'}), 400
    try:
        year = int(data.get('dob_year'))
        month = int(data.get('dob_month'))
        day = int(data.get('dob_day'))
        dob_date = date(year, month, day)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'A valid Date of Birth is required.'}), 400

    if 'photo' in request.files:
        photo = request.files['photo']
        if photo.filename != '':
            filename = secure_filename(photo.filename)
            unique_filename = f"{int(time.time())}_{filename}"
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
    profile.admin_mama_name = data.get('admin_mama_name')
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile updated successfully!'}), 200

@app.route('/api/profile/<int:profile_id>/delete', methods=['POST'])
def delete_profile(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    
    if profile.photo_url and 'default_avatar' not in profile.photo_url:
        try:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(profile.photo_url))
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception as e:
            print(f"Error deleting photo {profile.photo_url}: {e}")
            
    db.session.delete(profile)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile deleted successfully.'})

@app.route('/api/profile/<int:profile_id>/dispatch', methods=['POST'])
def dispatch_staff(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    data = request.json
    new_venue = data.get('venue')

    if new_venue == 'available':
        profile.current_venue = None
    elif new_venue in VENUE_LIST:
        profile.current_venue = new_venue
    else:
        return jsonify({'status': 'error', 'message': 'Invalid venue specified.'}), 400
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': f'{profile.nickname} dispatched to {new_venue}.'})

# --- Payroll API Endpoints ---
@app.route('/api/performance-record/', methods=['POST'])
def create_performance_record():
    data = request.json
    staff_id = data.get('staff_id')
    if not staff_id:
        return jsonify({'status': 'error', 'message': 'Staff ID is required.'}), 400
    
    today = date.today()
    existing_record = PerformanceRecord.query.filter_by(staff_id=staff_id, record_date=today).first()
    if existing_record:
        return jsonify({'status': 'error', 'message': 'A record for this staff member already exists for today.'}), 409

    new_record = PerformanceRecord(staff_id=staff_id, record_date=today)
    db.session.add(new_record)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Performance record created.',
        'record': new_record.to_dict()
    }), 201

@app.route('/api/performance-record/<int:record_id>', methods=['GET'])
def get_performance_record(record_id):
    record = PerformanceRecord.query.get_or_404(record_id)
    
    # Fetch last 5 historical records for the same staff member
    history = PerformanceRecord.query.filter(
        PerformanceRecord.staff_id == record.staff_id,
        PerformanceRecord.id != record.id # Exclude the current record
    ).order_by(PerformanceRecord.record_date.desc()).limit(5).all()
    
    history_dicts = [h.to_dict() for h in history]
    
    return jsonify({
        'status': 'success',
        'record': record.to_dict(),
        'history': history_dicts
    })

@app.route('/api/performance-record/<int:record_id>', methods=['POST'])
def update_performance_record(record_id):
    record = PerformanceRecord.query.get_or_404(record_id)
    data = request.json

    def time_from_string(time_str):
        if not time_str: return None
        try:
            return dt_time.fromisoformat(time_str)
        except (ValueError, TypeError):
            return None

    record.arrival_time = time_from_string(data.get('arrival_time'))
    record.departure_time = time_from_string(data.get('departure_time'))
    record.drinks_sold = int(data.get('drinks_sold', 0))
    record.special_commissions = float(data.get('special_commissions', 0))
    record.daily_salary = float(data.get('daily_salary', 800))
    record.other_deductions = float(data.get('other_deductions', 0))
    record.lateness_penalty = float(data.get('lateness_penalty', 0))

    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Record updated successfully.', 'record': record.to_dict()})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
