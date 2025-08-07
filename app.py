from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from datetime import datetime, date
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
    current_venue = db.Column(db.String(80), nullable=True) # New field for dispatch
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def age(self):
        if not self.dob: return None
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

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
    """Renders the dispatch board page."""
    all_staff = StaffProfile.query.all()
    
    # Sort staff into their respective venues or as available
    available_staff = [s for s in all_staff if not s.current_venue]
    dispatched_staff = {venue: [s for s in all_staff if s.current_venue == venue] for venue in VENUE_LIST}
    
    return render_template('dispatch.html', 
                           available_staff=available_staff, 
                           dispatched_staff=dispatched_staff, 
                           venues=VENUE_LIST)

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)