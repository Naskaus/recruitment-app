# app/models.py

from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime, time as dt_time, timedelta

# ==============================================================================
# NEW MODELS FOR MULTI-AGENCY V1.0
# ==============================================================================

class Agency(db.Model):
    __tablename__ = "agency"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    users = db.relationship('User', back_populates='agency', lazy='dynamic')
    staff_profiles = db.relationship('StaffProfile', back_populates='agency', lazy='dynamic')
    venues = db.relationship('Venue', back_populates='agency', lazy='dynamic')
    positions = db.relationship('AgencyPosition', back_populates='agency', lazy='dynamic')
    contracts = db.relationship('AgencyContract', back_populates='agency', lazy='dynamic')
    
    def __repr__(self):
        return f'<Agency {self.name}>'

class Venue(db.Model):
    __tablename__ = "venue"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    logo_url = db.Column(db.String(200), nullable=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('agency.id'), nullable=False)
    
    # Relationships
    agency = db.relationship('Agency', back_populates='venues')
    assignments = db.relationship('Assignment', back_populates='venue', lazy='dynamic')

    __table_args__ = (db.UniqueConstraint('name', 'agency_id', name='_name_agency_uc'),)
    
    def __repr__(self):
        return f'<Venue {self.name}>'

class AgencyPosition(db.Model):
    __tablename__ = "agency_position"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    agency_id = db.Column(db.Integer, db.ForeignKey('agency.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    agency = db.relationship('Agency', back_populates='positions')
    
    __table_args__ = (db.UniqueConstraint('name', 'agency_id', name='_position_name_agency_uc'),)
    
    def __repr__(self):
        return f'<AgencyPosition {self.name} for {self.agency.name}>'

class AgencyContract(db.Model):
    __tablename__ = "agency_contract"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    days = db.Column(db.Integer, nullable=False)
    agency_id = db.Column(db.Integer, db.ForeignKey('agency.id'), nullable=False)
    
    # Contract rules
    late_cutoff_time = db.Column(db.String(5), nullable=False, default="19:30")  # Format: HH:MM
    first_minute_penalty = db.Column(db.Float, nullable=False, default=0.0)
    additional_minute_penalty = db.Column(db.Float, nullable=False, default=5.0)
    drink_price = db.Column(db.Float, nullable=False, default=220.0)
    staff_commission = db.Column(db.Float, nullable=False, default=100.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    agency = db.relationship('Agency', back_populates='contracts')
    
    __table_args__ = (db.UniqueConstraint('name', 'agency_id', name='_contract_name_agency_uc'),)
    
    def __repr__(self):
        return f'<AgencyContract {self.name} ({self.days} days) for {self.agency.name}>'

class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    
    # Relationship
    users = db.relationship('User', back_populates='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'

# ==============================================================================
# UPDATED MODELS
# ==============================================================================

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    role = db.relationship('Role', back_populates='users')
    
    agency_id = db.Column(db.Integer, db.ForeignKey('agency.id'), nullable=True) # Nullable for WebDev
    agency = db.relationship('Agency', back_populates='users')

    managed_assignments = db.relationship('Assignment', foreign_keys='Assignment.managed_by_user_id', back_populates='manager')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    @property
    def role_name(self):
        return self.role.name if self.role else None

    def __repr__(self):
        return f'<User {self.username}>'

class StaffProfile(db.Model):
    __tablename__ = "staff_profile"
    id = db.Column(db.Integer, primary_key=True)
    
    agency_id = db.Column(db.Integer, db.ForeignKey('agency.id'), nullable=False)
    agency = db.relationship('Agency', back_populates='staff_profiles')

    staff_id = db.Column(db.String(10), nullable=True) 
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
    status = db.Column(db.String(50), nullable=False, default='Screening')
    photo_url = db.Column(db.String(200), default='default_avatar.png')
    admin_mama_name = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    preferred_position = db.Column(db.String(80), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    assignments = db.relationship('Assignment', back_populates='staff', lazy=True)

    __table_args__ = (db.UniqueConstraint('staff_id', 'agency_id', name='_staff_id_agency_uc'),)

    @property
    def age(self):
        if not self.dob:
            return None
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (today.month, today.day))

class Assignment(db.Model):
    __tablename__ = 'assignment'
    id = db.Column(db.Integer, primary_key=True)
    
    agency_id = db.Column(db.Integer, db.ForeignKey('agency.id'), nullable=False)

    staff_id = db.Column(db.Integer, db.ForeignKey('staff_profile.id'), nullable=True)
    staff = db.relationship('StaffProfile', back_populates='assignments')
    
    managed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    archived_staff_name = db.Column(db.String(100), nullable=True)
    archived_staff_photo = db.Column(db.String(200), nullable=True)
    
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=True)
    venue = db.relationship('Venue', back_populates='assignments')
    
    contract_role = db.Column(db.String(50), nullable=False, server_default='Dancer')
    contract_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    base_salary = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    manager = db.relationship('User', back_populates='managed_assignments')
    
    # --- CORRECTED: Replaced backref with back_populates ---
    performance_records = db.relationship('PerformanceRecord', back_populates='assignment', lazy=True, cascade="all, delete-orphan")
    contract_calculations = db.relationship('ContractCalculations', back_populates='assignment', uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, "staff_id": self.staff_id, 
            "venue": self.venue.name if self.venue else None,
            "role": self.contract_role,
            "contract_type": self.contract_type, "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(), "base_salary": self.base_salary,
            "status": self.status,
        }

class PerformanceRecord(db.Model):
    __tablename__ = 'performance_record'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    
    # --- CORRECTED: Added explicit relationship to Assignment ---
    assignment = db.relationship('Assignment', back_populates='performance_records')

    record_date = db.Column(db.Date, nullable=False, default=date.today)
    arrival_time = db.Column(db.Time, nullable=True)
    departure_time = db.Column(db.Time, nullable=True)
    drinks_sold = db.Column(db.Integer, default=0)
    special_commissions = db.Column(db.Float, default=0.0)
    bonus = db.Column(db.Float, default=0.0)
    malus = db.Column(db.Float, default=0.0)
    lateness_penalty = db.Column(db.Float, default=0.0)
    daily_salary = db.Column(db.Float, default=0.0)
    daily_profit = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('assignment_id', 'record_date', name='uq_assignment_date'),)

    def to_dict(self):
        return {
            "id": self.id, "assignment_id": self.assignment_id, "record_date": self.record_date.isoformat(),
            "arrival_time": self.arrival_time.strftime('%H:%M') if self.arrival_time else None,
            "departure_time": self.departure_time.strftime('%H:%M') if self.departure_time else None,
            "drinks_sold": self.drinks_sold, "special_commissions": self.special_commissions,
            "bonus": self.bonus, "malus": self.malus, "lateness_penalty": self.lateness_penalty,
            "daily_salary": self.daily_salary, "daily_profit": self.daily_profit,
        }

class ContractCalculations(db.Model):
    __tablename__ = 'contract_calculations'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False, unique=True)
    
    # Calculated totals
    total_salary = db.Column(db.Float, default=0.0)
    total_commission = db.Column(db.Float, default=0.0)
    total_profit = db.Column(db.Float, default=0.0)
    days_worked = db.Column(db.Integer, default=0)
    total_drinks = db.Column(db.Integer, default=0)
    total_special_comm = db.Column(db.Float, default=0.0)
    
    # Timestamp
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    assignment = db.relationship('Assignment', back_populates='contract_calculations', uselist=False)
    
    def __repr__(self):
        return f'<ContractCalculations for Assignment {self.assignment_id}>'