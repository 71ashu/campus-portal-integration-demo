"""Database models for the AI Course Advisor (portal-integration demo).

Identical in shape to the standalone AI-Course-Advisor project's models,
minus password-reset (this demo authenticates via mock campus SSO, not
passwords) and with a few added columns that track where a student's data
came from: `sis_id`, `sis_synced_at`, `sis_unmet_requirements`. Everything
else — Course, Program, StudentCourse, Conversation, Message — is what
services.py / knowledge_graph.py / collaborative.py / grade_predictor.py
already expect, unmodified.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class ProgramCourse(db.Model):
    """Junction table linking programs to their courses (many-to-many)."""
    __tablename__ = 'program_courses'

    program_id = db.Column(db.String(50), db.ForeignKey('programs.program_id', ondelete='CASCADE'), primary_key=True)
    course_id = db.Column(db.String(20), db.ForeignKey('courses.id', ondelete='CASCADE'), primary_key=True)

    program = db.relationship('Program', backref=db.backref('program_courses', lazy='dynamic'))
    course = db.relationship('Course', backref=db.backref('program_courses', lazy='dynamic'))


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    units = db.Column(db.Integer, default=3)
    level = db.Column(db.String(50))
    description = db.Column(db.Text)
    department = db.Column(db.String(100))
    prerequisites = db.Column(db.JSON, default=list)
    alt_codes = db.Column(db.JSON, default=list)

    # Legacy fields retained for compatibility with services.py / seed data shape.
    difficulty = db.Column(db.String(20))
    topics = db.Column(db.JSON, default=list)

    def to_dict(self):
        return {
            'course_number': self.id,
            'course_name': self.name,
            'units': self.units,
            'level': self.level or '',
            'description': self.description or '',
            'department': self.department or '',
            'prerequisites': self.prerequisites or [],
            'alt_codes': self.alt_codes or [],
        }


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    name = db.Column(db.String(100), nullable=False)
    university = db.Column(db.String(200), default='Unknown University')
    program_enrolled = db.Column(db.String(200), default='Undeclared')
    major = db.Column(db.String(100), default='Computer Science')
    year = db.Column(db.String(20), default='Sophomore')
    interests = db.Column(db.JSON, default=list)
    career_goals = db.Column(db.String(500))
    program_gpa = db.Column(db.Float, default=0.0)
    is_synthetic = db.Column(db.Boolean, default=False)
    onboarding_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Integration provenance: where this student's record comes from ---
    sis_id = db.Column(db.String(50), unique=True, nullable=True, index=True)
    sis_synced_at = db.Column(db.DateTime, nullable=True)
    sis_unmet_requirements = db.Column(db.JSON, default=list)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)

    def to_dict(self):
        completed = StudentCourse.query.filter_by(student_id=self.id, status='completed').all()
        current = StudentCourse.query.filter_by(student_id=self.id, status='current').all()
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'university': self.university or '',
            'program': self.program_enrolled or '',
            'major': self.major,
            'year': self.year,
            'interests': self.interests or [],
            'careerGoals': self.career_goals or '',
            'programGPA': self.program_gpa if self.program_gpa is not None else 0.0,
            'onboardingCompleted': self.onboarding_completed or False,
            'completedCourses': [sc.course_id for sc in completed],
            'currentCourses': [sc.course_id for sc in current],
            'sisId': self.sis_id,
            'sisSyncedAt': self.sis_synced_at.isoformat() if self.sis_synced_at else None,
        }


class Program(db.Model):
    __tablename__ = 'programs'

    program_id = db.Column(db.String(50), primary_key=True)
    program_name = db.Column(db.String(200), nullable=False)
    degree_type = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(200))
    description = db.Column(db.Text)
    total_units_required = db.Column(db.Integer)
    minimum_gpa = db.Column(db.Float)

    requirements = db.Column(db.JSON, default=dict)
    concentrations = db.Column(db.JSON, default=list)
    learning_outcomes = db.Column(db.JSON, default=list)
    admission_requirements = db.Column(db.JSON, default=dict)
    special_features = db.Column(db.JSON, default=list)
    time_limit = db.Column(db.String(200))

    def to_dict(self):
        return {
            'program_id': self.program_id,
            'program_name': self.program_name,
            'degree_type': self.degree_type,
            'department': self.department,
            'description': self.description,
            'total_units_required': self.total_units_required,
            'minimum_gpa': self.minimum_gpa,
            'requirements': self.requirements or {},
            'concentrations': self.concentrations or [],
            'learning_outcomes': self.learning_outcomes or [],
            'admission_requirements': self.admission_requirements or {},
            'special_features': self.special_features or [],
            'time_limit': self.time_limit,
        }


class Conversation(db.Model):
    __tablename__ = 'conversations'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True,
    )
    title = db.Column(db.String(200), nullable=False, default='New conversation')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('conversations', lazy='dynamic'))
    messages = db.relationship(
        'Message', backref='conversation', order_by='Message.created_at, Message.id',
        cascade='all, delete-orphan', lazy='dynamic',
    )

    def to_dict(self, include_messages=False):
        message_rows = self.messages.all()
        data = {
            'id': self.id,
            'title': self.title,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
            'messageCount': len(message_rows),
        }
        if include_messages:
            data['messages'] = [m.to_dict() for m in message_rows]
        return data


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True,
    )
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False, default='')
    recommendations = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content or '',
            'recommendations': self.recommendations or [],
            'createdAt': self.created_at.isoformat() if self.created_at else None,
        }


class StudentCourse(db.Model):
    __tablename__ = 'student_courses'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_id = db.Column(db.String(20), db.ForeignKey('courses.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'completed' or 'current'
    final_score = db.Column(db.Float)
    final_letter = db.Column(db.String(5))
    course_gpa = db.Column(db.Float)
    grade_points = db.Column(db.Float)

    student = db.relationship('Student', backref=db.backref('enrollments', lazy='dynamic'))
    course = db.relationship('Course', backref=db.backref('enrollments', lazy='dynamic'))
