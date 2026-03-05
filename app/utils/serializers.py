"""
Rôle du fichier:
Convertit les entités SQLAlchemy en dictionnaires JSON renvoyés par les endpoints API.
"""

from app.models import Attendance, Contract, Department, Employee, Leave, Message, Payroll, Role


def employee_to_dict(employee: Employee) -> dict:
    """Convertit un objet Employee en JSON exploitable par le frontend."""
    return {
        "id": employee.id,
        "matricule": employee.matricule,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "photo_url": employee.photo_url,
        "email": employee.email,
        "phone": employee.phone,
        "address": employee.address,
        "hire_date": employee.hire_date.isoformat(),
        "status": employee.status,
        "department_id": employee.department_id,
        "role_id": employee.role_id,
        "department": employee.department.name if employee.department else None,
        "role": employee.role.name if employee.role else None,
        "account_username": employee.user.username if employee.user else None,
    }


def department_to_dict(department: Department) -> dict:
    """Convertit un objet Department en dictionnaire JSON."""
    return {
        "id": department.id,
        "name": department.name,
        "budget": department.budget,
        "manager_id": department.manager_id,
        "employees": [employee_to_dict(emp) for emp in department.employees],
    }


def role_to_dict(role: Role) -> dict:
    """Convertit un rôle et ses permissions en structure JSON."""
    return {
        "id": role.id,
        "name": role.name,
        "permissions": [p.name for p in role.permissions],
    }


def payroll_to_dict(payroll: Payroll) -> dict:
    """Convertit une fiche de paie en dictionnaire sérialisable."""
    return {
        "id": payroll.id,
        "employee_id": payroll.employee_id,
        "employee_name": f"{payroll.employee.first_name} {payroll.employee.last_name}",
        "base_salary": payroll.base_salary,
        "bonus": payroll.bonus,
        "overtime_hours": payroll.overtime_hours,
        "deductions": payroll.deductions,
        "taxes": payroll.taxes,
        "net_salary": payroll.net_salary,
        "payroll_month": payroll.paid_at.strftime("%Y-%m"),
        "paid_at": payroll.paid_at.isoformat(),
    }


def attendance_to_dict(attendance: Attendance) -> dict:
    """Convertit un pointage en dictionnaire JSON."""
    return {
        "id": attendance.id,
        "employee_id": attendance.employee_id,
        "check_in": attendance.check_in.isoformat(),
        "check_out": attendance.check_out.isoformat() if attendance.check_out else None,
        "worked_hours": attendance.worked_hours,
        "late_minutes": attendance.late_minutes,
        "is_absent": attendance.is_absent,
    }


def leave_to_dict(leave: Leave) -> dict:
    """Convertit une demande de congé en dictionnaire JSON."""
    return {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "reason": leave.reason,
        "status": leave.status,
        "decision_comment": leave.decision_comment,
    }


def contract_to_dict(contract: Contract) -> dict:
    """Convertit un contrat en dictionnaire JSON."""
    return {
        "id": contract.id,
        "employee_id": contract.employee_id,
        "contract_type": contract.contract_type,
        "start_date": contract.start_date.isoformat(),
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "contractual_salary": contract.contractual_salary,
        "document_path": contract.document_path,
    }


def message_to_dict(message: Message) -> dict:
    """Convertit un message interne en dictionnaire enrichi (noms, lecture, timestamps)."""
    sender = message.sender
    recipient = message.recipient
    sender_employee = sender.employee if sender else None
    recipient_employee = recipient.employee if recipient else None

    sender_name = (
        f"{sender_employee.first_name} {sender_employee.last_name}" if sender_employee else (sender.username if sender else "-")
    )
    recipient_name = (
        f"{recipient_employee.first_name} {recipient_employee.last_name}"
        if recipient_employee
        else (recipient.username if recipient else "-")
    )

    return {
        "id": message.id,
        "sender_user_id": message.sender_user_id,
        "recipient_user_id": message.recipient_user_id,
        "sender_username": sender.username if sender else None,
        "recipient_username": recipient.username if recipient else None,
        "sender_name": sender_name,
        "recipient_name": recipient_name,
        "subject": message.subject,
        "content": message.content,
        "sent_at": message.sent_at.isoformat(),
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "read_at": message.read_at.isoformat() if message.read_at else None,
        "is_read": message.read_at is not None,
    }
