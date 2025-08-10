from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from datetime import datetime, date, time as dt_time, timedelta
from werkzeug.utils import secure_filename

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

# =========================
# Models
# =========================

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
    admin_mama_name = db.Column(db.String(80))
    # NOTE: kept for legacy dispatch UI
    current_venue = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # New contract relationship
    assignments = db.relationship('Assignment', backref='staff', lazy=True, cascade="all, delete-orphan")

    @property
    def age(self):
        if not self.dob:
            return None
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))


# --- Contract system ---

CONTRACT_TYPES = {"1jour": 1, "10jours": 10, "1mois": 30}  # inclusive number of days

def compute_end_date(start_date: date, contract_type: str) -> date:
    days = CONTRACT_TYPES.get(contract_type)
    if not days:
        raise ValueError("Invalid contract_type")
    return start_date + timedelta(days=days - 1)  # inclusive

def calc_lateness_penalty(arrival_time):
    """Late after 19:30 => 5 THB per minute."""
    if not arrival_time:
        return 0
    cutoff = dt_time(19, 30)
    if arrival_time <= cutoff:
        return 0
    minutes = (datetime.combine(date.today(), arrival_time) - datetime.combine(date.today(), cutoff)).seconds // 60
    return minutes * 5

class Assignment(db.Model):
    __tablename__ = 'assignment'
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff_profile.id'), nullable=False)
    venue = db.Column(db.String(80), nullable=False)
    contract_type = db.Column(db.String(20), nullable=False)  # '1jour' | '10jours' | '1mois'
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    base_salary = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='ongoing')  # ongoing | completed | canceled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    performance_records = db.relationship(
        'PerformanceRecord',
        backref='assignment',
        lazy=True,
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "staff_id": self.staff_id,
            "venue": self.venue,
            "contract_type": self.contract_type,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "base_salary": self.base_salary,
            "status": self.status,
        }

class PerformanceRecord(db.Model):
    __tablename__ = 'performance_record'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    record_date = db.Column(db.Date, nullable=False, default=date.today)

    arrival_time = db.Column(db.Time, nullable=True)
    departure_time = db.Column(db.Time, nullable=True)

    drinks_sold = db.Column(db.Integer, default=0)           # 100 to staff, 120 to bar per drink
    special_commissions = db.Column(db.Float, default=0.0)   # extra bar revenue
    bonus = db.Column(db.Float, default=0.0)                 # + staff
    malus = db.Column(db.Float, default=0.0)                 # - staff
    lateness_penalty = db.Column(db.Float, default=0.0)      # auto from arrival

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('assignment_id', 'record_date', name='uq_assignment_date'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "assignment_id": self.assignment_id,
            "record_date": self.record_date.isoformat(),
            "arrival_time": self.arrival_time.strftime('%H:%M') if self.arrival_time else None,
            "departure_time": self.departure_time.strftime('%H:%M') if self.departure_time else None,
            "drinks_sold": self.drinks_sold,
            "special_commissions": self.special_commissions,
            "bonus": self.bonus,
            "malus": self.malus,
            "lateness_penalty": self.lateness_penalty,
        }

# =========================
# Views
# =========================

@app.route('/')
@app.route('/staff')
def staff_list():
    all_profiles = StaffProfile.query.order_by(StaffProfile.created_at.desc()).all()
    statuses = ["Active", "On assignment", "Quiet (recent)", "Moderately active", "On holiday", "Inactive (long time)"]
    return render_template('staff_list.html', profiles=all_profiles, statuses=statuses)

@app.route('/dispatch')
def dispatch_board():
    # Legacy: still uses current_venue to render columns
    all_staff = StaffProfile.query.all()
    available_staff = [s for s in all_staff if not s.current_venue]
    dispatched_staff = {venue: [s for s in all_staff if s.current_venue == venue] for venue in VENUE_LIST}
    return render_template('dispatch.html', available_staff=available_staff, dispatched_staff=dispatched_staff, venues=VENUE_LIST)

@app.route('/payroll')
def payroll_page_new():
    """New payroll lists ongoing assignments; template will be updated next."""
    venue = request.args.get('venue')
    q = Assignment.query.filter_by(status='ongoing')
    if venue:
        q = q.filter(Assignment.venue == venue)
    ongoing = q.order_by(Assignment.start_date.asc()).all()
    rows = [{"assignment": a, "contract_days": (a.end_date - a.start_date).days + 1} for a in ongoing]
    return render_template('payroll.html', assignments=rows, venues=VENUE_LIST, selected_venue=venue)

# ---------- Profile pages (NEW: restored) ----------

@app.route('/profile/new', methods=['GET'])
def new_profile_form():
    current_year = date.today().year
    years = range(current_year - 18, current_year - 60, -1)
    months = range(1, 13)
    days = range(1, 32)
    return render_template(
        'profile_form.html',
        years=years, months=months, days=days,
        admins=ADMIN_LIST,
        edit_mode=False
    )

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
    return render_template(
        'profile_form.html',
        profile=profile,
        years=years, months=months, days=days,
        admins=ADMIN_LIST,
        edit_mode=True
    )


# =========================
# Profiles API
# =========================

@app.route('/api/profile', methods=['POST'])
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

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Legacy dispatch API
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

# =========================
# Assignment API
# =========================

@app.route('/api/assignment', methods=['POST'])
def create_assignment():
    data = request.get_json() or {}
    try:
        staff_id = int(data.get('staff_id'))
        venue = data.get('venue')
        contract_type = data.get('contract_type')
        start_date = datetime.fromisoformat(data.get('start_date')).date()
        base_salary = float(data.get('base_salary', 0))
    except Exception:
        return jsonify({"status": "error", "message": "Invalid payload."}), 400

    if venue not in VENUE_LIST:
        return jsonify({"status": "error", "message": "Invalid venue."}), 400
    if contract_type not in CONTRACT_TYPES:
        return jsonify({"status": "error", "message": "Invalid contract_type."}), 400

    staff = StaffProfile.query.get(staff_id)
    if not staff:
        return jsonify({"status": "error", "message": "Staff not found."}), 404

    # Prevent overlapping ongoing contracts for same staff
    overlapping = Assignment.query.filter(
        Assignment.staff_id == staff_id,
        Assignment.status == 'ongoing',
        Assignment.start_date <= start_date,
        Assignment.end_date >= start_date
    ).first()
    if overlapping:
        return jsonify({"status": "error", "message": "Staff already has an ongoing contract overlapping this start date."}), 409

    end_date = compute_end_date(start_date, contract_type)
    new_a = Assignment(
        staff_id=staff_id,
        venue=venue,
        contract_type=contract_type,
        start_date=start_date,
        end_date=end_date,
        base_salary=base_salary,
        status='ongoing'
    )
    db.session.add(new_a)

    # 🚀 IMPORTANT: keep legacy dispatch board in sync
    staff.current_venue = venue

    db.session.commit()
    return jsonify({"status": "success", "assignment": new_a.to_dict()}), 201


# === Assignment management: end now & delete ===

@app.route('/api/assignment/<int:assignment_id>/end', methods=['POST'])
def end_assignment_now(assignment_id):
    """Mark an ongoing assignment as completed today."""
    a = Assignment.query.get_or_404(assignment_id)

    if a.status != 'ongoing':
        return jsonify({"status": "error", "message": "Assignment is not ongoing."}), 400

    today = date.today()
    # end_date should not be before start_date
    a.end_date = today if today >= a.start_date else a.start_date
    a.status = 'completed'
    db.session.commit()

    return jsonify({"status": "success", "assignment": a.to_dict()}), 200


@app.route('/api/assignment/<int:assignment_id>', methods=['DELETE'])
def delete_assignment(assignment_id):
    """Delete an assignment and its performance records (cascade)."""
    a = Assignment.query.get_or_404(assignment_id)

    # Optional: forbid deleting a completed assignment (business-dependent)
    # if a.status == 'completed':
    #     return jsonify({"status": "error", "message": "Cannot delete a completed assignment."}), 400

    db.session.delete(a)  # performance_records removed via cascade
    db.session.commit()
    return jsonify({"status": "success"}), 200


# =========================
# Performance API
# =========================

def _get_or_create_daily_record(assignment_id: int, ymd: date) -> 'PerformanceRecord':
    rec = PerformanceRecord.query.filter_by(assignment_id=assignment_id, record_date=ymd).first()
    if rec:
        return rec
    rec = PerformanceRecord(assignment_id=assignment_id, record_date=ymd)
    db.session.add(rec)
    db.session.commit()
    return rec

@app.route('/api/performance/<int:assignment_id>/<string:ymd>', methods=['GET'])
def get_performance(assignment_id, ymd):
    try:
        day = datetime.fromisoformat(ymd).date()
    except Exception:
        return jsonify({"status": "error", "message": "Invalid date."}), 400
    rec = PerformanceRecord.query.filter_by(assignment_id=assignment_id, record_date=day).first()
    if not rec:
        return jsonify({"status": "success", "record": None, "history": []}), 200
    history = PerformanceRecord.query.filter(
        PerformanceRecord.assignment_id == assignment_id,
        PerformanceRecord.id != rec.id
    ).order_by(PerformanceRecord.record_date.desc()).limit(5).all()
    return jsonify({"status": "success", "record": rec.to_dict(), "history": [h.to_dict() for h in history]}), 200

@app.route('/api/performance/<int:assignment_id>', methods=['GET'])
def list_performance_for_assignment(assignment_id):
    """
    Return all saved daily records for a given assignment (most recent first).
    This lets the UI render a persistent history list.
    """
    a = Assignment.query.get(assignment_id)
    if not a:
        return jsonify({"status": "error", "message": "Assignment not found."}), 404

    records = (PerformanceRecord.query
               .filter_by(assignment_id=assignment_id)
               .order_by(PerformanceRecord.record_date.desc())
               .all())

    return jsonify({
        "status": "success",
        "records": [r.to_dict() for r in records],
        # contract meta (useful for client-side calculations)
        "contract": {
            "start_date": a.start_date.isoformat(),
            "end_date": a.end_date.isoformat(),
            "base_salary": a.base_salary,
            "contract_days": (a.end_date - a.start_date).days + 1
        }
    }), 200

# --- NEW: Full history with optional ?days filter ---
@app.route('/api/performance-history/<int:assignment_id>', methods=['GET'])
def performance_history(assignment_id):
    """
    Return performance history for an assignment, optionally limited to the last N days.

    Querystring:
      - days (optional, int): number of days to look back from today (inclusive).
        If omitted or invalid, defaults to 120. Values <1 are ignored.
    """
    a = Assignment.query.get(assignment_id)
    if not a:
        return jsonify({"status": "error", "message": "Assignment not found."}), 404

    # Parse and clamp 'days'
    days = request.args.get('days', default=120, type=int)
    if days is None or days < 1:
        days = 120

    since = date.today() - timedelta(days=days - 1)

    q = PerformanceRecord.query.filter_by(assignment_id=assignment_id)
    # Only apply time window if 'days' is provided (here it always is, with default 120)
    q = q.filter(PerformanceRecord.record_date >= since)

    records = q.order_by(PerformanceRecord.record_date.desc()).all()

    return jsonify({
        "status": "success",
        "records": [r.to_dict() for r in records],
        "contract": {
            "start_date": a.start_date.isoformat(),
            "end_date": a.end_date.isoformat(),
            "base_salary": a.base_salary,
            "contract_days": (a.end_date - a.start_date).days + 1
        },
        "window": {
            "days": days,
            "since": since.isoformat(),
            "today": date.today().isoformat()
        }
    }), 200

@app.route('/api/performance', methods=['POST'])
def upsert_performance():
    data = request.get_json() or {}
    try:
        assignment_id = int(data.get('assignment_id'))
        ymd = datetime.fromisoformat(data.get('record_date')).date()
    except Exception:
        return jsonify({"status": "error", "message": "Invalid assignment_id or record_date"}), 400

    a = Assignment.query.get(assignment_id)
    if not a or a.status != 'ongoing':
        return jsonify({"status": "error", "message": "Assignment not found or not ongoing."}), 404
    if not (a.start_date <= ymd <= a.end_date):
        return jsonify({"status": "error", "message": "Date outside contract period."}), 400

    rec = _get_or_create_daily_record(assignment_id, ymd)

    def time_or_none(s):
        if not s:
            return None
        try:
            return dt_time.fromisoformat(s)
        except Exception:
            return None

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
# Main
# =========================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
