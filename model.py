from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from enum import Enum
from datetime import datetime

db = SQLAlchemy()

# --- ENUM DEFINITIONS ---

class UserRole(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"

class LeadStatus(Enum):
    NEW = "New"  # Added as starting point
    REQUIREMENT_UNDERSTOOD = "Requirement Understood"
    MEASUREMENT_SCHEDULED = "Measurement Scheduled"
    QUOTATION_SENT = "Quotation Sent"
    FOLLOW_UP = "Follow Up"
    ORDER_CONFIRMED = "Order Confirmed"
    IN_PRODUCTION = "In Production"
    READY_FOR_DISPATCH = "Ready for Dispatch"
    INSTALLATION_SCHEDULED = "Installation Scheduled"
    INSTALLATION_DONE = "Installation Done"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class CustomerStatus(Enum):
    NEW = "New"
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PROSPECT = "Prospect"

class LeadSource(Enum):
    WEBSITE = "Website"
    GOOGLE = "Google"
    SOCIAL_MEDIA = "Social Media"
    REFERRAL = "Referral"
    WALK_IN = "Walk-in"
    OTHER = "Other"

class ActivityType(Enum):
    CALL = "Call"
    MEETING = "Meeting"
    EMAIL = "Email"
    NOTE = "Note"
    TASK = "Task"

# --- MODELS ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False) # Supports Argon2/BCrypt hashes
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=True)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.EMPLOYEE)
    
    # 1-to-1 relationship with Employee profile
    employee = db.relationship('Employee', back_populates='user', uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(50), nullable=True)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Relationship to User
    user = db.relationship('User', back_populates='employee')

    @property
    def email(self):
        return self.user.email if self.user else None

    @property
    def phone_number(self):
        return self.user.phone_number if self.user else None

    def __repr__(self):
        return f'<Employee {self.name}>'

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    company = db.Column(db.String(100), nullable=True)
    source = db.Column(db.Enum(LeadSource), default=LeadSource.OTHER)
    status = db.Column(db.Enum(LeadStatus), default=LeadStatus.NEW, index=True)
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    is_deleted = db.Column(db.Boolean, default=False)

    # Foreign Keys
    assigned_to = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False, index=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True, index=True)

    # Relationships
    assignee = db.relationship('Employee', foreign_keys=[assigned_to], backref='assigned_leads')
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='leads_created')
    updater = db.relationship('Employee', foreign_keys=[updated_by], backref='leads_updated')

    @property
    def status_display(self):
        return self.status.value if self.status else ""

    def __repr__(self):
        return f'<Lead {self.name}>'

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), unique=True, nullable=True, index=True)
    
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    address = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    company = db.Column(db.String(100), nullable=True)
    source = db.Column(db.Enum(LeadSource), default=LeadSource.OTHER)
    status = db.Column(db.Enum(CustomerStatus), default=CustomerStatus.ACTIVE, index=True)
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    is_deleted = db.Column(db.Boolean, default=False)

    # Foreign Keys
    assigned_to = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False, index=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True, index=True)

    # Relationships
    lead = db.relationship('Lead', backref=db.backref('converted_customer', uselist=False))
    assignee = db.relationship('Employee', foreign_keys=[assigned_to], backref='assigned_customers')
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='customers_created')
    updater = db.relationship('Employee', foreign_keys=[updated_by], backref='customers_updated')

    @property
    def status_display(self):
        return self.status.value if self.status else ""

    def __repr__(self):
        return f'<Customer {self.name}>'

class LeadActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False, index=True)
    activity_type = db.Column(db.Enum(ActivityType), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    created_by = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False, index=True)

    # Relationships
    lead = db.relationship('Lead', backref=db.backref('activities', cascade='all, delete-orphan'))
    creator = db.relationship('Employee', foreign_keys=[created_by], backref='activities_created')

    def __repr__(self):
        return f'<LeadActivity {self.activity_type.name} for Lead {self.lead_id}>'