"""
Rôle du fichier:
Définit la structure des tables SQLAlchemy (utilisateurs, employés, congés, messages, etc.)
et leurs relations en base de données.
"""

from __future__ import annotations

from datetime import datetime, date
from enum import Enum

from app.extensions import db


role_permission = db.Table(
    "role_permission",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class EmployeeStatus(str, Enum):
    """Classe EmployeeStatus : documente ses responsabilites et son comportement."""
    ACTIVE = "Actif"
    SUSPENDED = "Suspendu"
    RESIGNED = "Démissionné"


class ContractType(str, Enum):
    """Classe ContractType : documente ses responsabilites et son comportement."""
    CDI = "CDI"
    CDD = "CDD"
    INTERN = "Stage"


class User(db.Model):
    """Classe User : documente ses responsabilites et son comportement."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    must_change_password = db.Column(db.Boolean, nullable=False, default=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)

    role = db.relationship("Role", back_populates="users")
    employee = db.relationship("Employee", back_populates="user", uselist=False)
    sent_messages = db.relationship(
        "Message",
        foreign_keys="Message.sender_user_id",
        back_populates="sender",
        lazy=True,
        cascade="all, delete-orphan",
    )
    received_messages = db.relationship(
        "Message",
        foreign_keys="Message.recipient_user_id",
        back_populates="recipient",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Role(db.Model):
    """Classe Role : documente ses responsabilites et son comportement."""
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    users = db.relationship("User", back_populates="role", lazy=True)
    employees = db.relationship("Employee", back_populates="role", lazy=True)
    permissions = db.relationship("Permission", secondary=role_permission, lazy="joined")


class Permission(db.Model):
    """Classe Permission : documente ses responsabilites et son comportement."""
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)


class Department(db.Model):
    """Classe Department : documente ses responsabilites et son comportement."""
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    budget = db.Column(db.Float, nullable=False, default=0.0)
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)

    employees = db.relationship("Employee", back_populates="department", lazy=True, foreign_keys="Employee.department_id")


class Employee(db.Model):
    """Classe Employee : documente ses responsabilites et son comportement."""
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    matricule = db.Column(db.String(40), nullable=True)
    photo_url = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    hire_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), nullable=False, default=EmployeeStatus.ACTIVE.value)

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)

    department = db.relationship("Department", back_populates="employees", foreign_keys=[department_id])
    role = db.relationship("Role", back_populates="employees")
    user = db.relationship("User", back_populates="employee", uselist=False, lazy=True)

    payrolls = db.relationship("Payroll", back_populates="employee", lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship("Attendance", back_populates="employee", lazy=True, cascade="all, delete-orphan")
    leaves = db.relationship("Leave", back_populates="employee", lazy=True, cascade="all, delete-orphan")
    contracts = db.relationship("Contract", back_populates="employee", lazy=True, cascade="all, delete-orphan")


class Payroll(db.Model):
    """Classe Payroll : documente ses responsabilites et son comportement."""
    __tablename__ = "payrolls"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    base_salary = db.Column(db.Float, nullable=False)
    bonus = db.Column(db.Float, nullable=False, default=0.0)
    overtime_hours = db.Column(db.Float, nullable=False, default=0.0)
    deductions = db.Column(db.Float, nullable=False, default=0.0)
    taxes = db.Column(db.Float, nullable=False, default=0.0)
    net_salary = db.Column(db.Float, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employee = db.relationship("Employee", back_populates="payrolls")


class Attendance(db.Model):
    """Classe Attendance : documente ses responsabilites et son comportement."""
    __tablename__ = "attendances"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=True)
    worked_hours = db.Column(db.Float, nullable=False, default=0.0)
    late_minutes = db.Column(db.Integer, nullable=False, default=0)
    is_absent = db.Column(db.Boolean, nullable=False, default=False)

    employee = db.relationship("Employee", back_populates="attendances")


class Leave(db.Model):
    """Classe Leave : documente ses responsabilites et son comportement."""
    __tablename__ = "leaves"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(40), nullable=False, default="En attente")
    decision_comment = db.Column(db.String(500), nullable=True)

    employee = db.relationship("Employee", back_populates="leaves")


class Contract(db.Model):
    """Classe Contract : documente ses responsabilites et son comportement."""
    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    contract_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    contractual_salary = db.Column(db.Float, nullable=False)
    document_path = db.Column(db.String(255), nullable=True)

    employee = db.relationship("Employee", back_populates="contracts")


class ActivityLog(db.Model):
    """Classe ActivityLog : documente ses responsabilites et son comportement."""
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Message(db.Model):
    """Classe Message : documente ses responsabilites et son comportement."""
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(160), nullable=True)
    content = db.Column(db.String(2000), nullable=False)
    sent_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    edited_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_user_id], back_populates="sent_messages")
    recipient = db.relationship("User", foreign_keys=[recipient_user_id], back_populates="received_messages")
