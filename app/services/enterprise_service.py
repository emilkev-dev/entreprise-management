"""
Rôle du fichier:
Centralise la logique métier principale de l'ERP (employés, paie, congés, messages, rapports, etc.).
"""

from __future__ import annotations

from datetime import datetime, date, timedelta
from calendar import monthrange

import pandas as pd
from flask import current_app
from sqlalchemy import func, or_

from app.exceptions import NotFoundException, ValidationException
from app.extensions import db
from app.models import Attendance, Contract, Department, Employee, EmployeeStatus, Leave, Message, Payroll, Permission, Role, User
from app.utils.security import hash_password


def _is_active_employee_status(status: str | None) -> bool:
    """Fonction _is_active_employee_status : execute une partie de la logique applicative."""
    normalized = (status or "").strip().lower()
    return normalized in {"actif", "act", "active"}


def _user_display_name(user: User | None) -> str:
    """Fonction _user_display_name : execute une partie de la logique applicative."""
    if not user:
        return "Utilisateur"
    if user.employee:
        return f"{user.employee.first_name} {user.employee.last_name}"
    return user.username


class EnterpriseService:
    """Service métier principal de l'ERP (RH, paie, congés, messagerie, reporting)."""

    @staticmethod
    def message_edit_window_minutes() -> int:
        """Methode message_edit_window_minutes : realise une partie de la logique de la classe."""
        minutes = int(current_app.config.get("MESSAGE_EDIT_DELETE_WINDOW_MINUTES", 15) or 15)
        return max(1, minutes)

    @staticmethod
    def _message_action_deadline(message: Message) -> datetime:
        """Methode _message_action_deadline : realise une partie de la logique de la classe."""
        return message.sent_at + timedelta(minutes=EnterpriseService.message_edit_window_minutes())

    @staticmethod
    def message_action_remaining_seconds(user_id: int, message: Message) -> int:
        """Methode message_action_remaining_seconds : realise une partie de la logique de la classe."""
        if message.sender_user_id != user_id:
            return 0
        remaining = int((EnterpriseService._message_action_deadline(message) - datetime.utcnow()).total_seconds())
        return max(0, remaining)

    @staticmethod
    def can_edit_or_delete_message(user_id: int, message: Message) -> bool:
        """Methode can_edit_or_delete_message : realise une partie de la logique de la classe."""
        return EnterpriseService.message_action_remaining_seconds(user_id, message) > 0

    @staticmethod
    def list_conversations(user_id: int, query: str | None = None) -> list[dict]:
        """Methode list_conversations : realise une partie de la logique de la classe."""
        messages = (
            Message.query.filter(
                or_(
                    Message.sender_user_id == user_id,
                    Message.recipient_user_id == user_id,
                )
            )
            .order_by(Message.sent_at.desc())
            .limit(800)
            .all()
        )

        unread_rows = (
            db.session.query(Message.sender_user_id, func.count(Message.id))
            .filter(
                Message.recipient_user_id == user_id,
                Message.read_at.is_(None),
            )
            .group_by(Message.sender_user_id)
            .all()
        )
        unread_by_user = {int(sender_id): int(count) for sender_id, count in unread_rows}

        conversations: dict[int, dict] = {}
        for message in messages:
            other_user_id = (
                message.recipient_user_id if message.sender_user_id == user_id else message.sender_user_id
            )
            if other_user_id in conversations:
                continue

            other_user = User.query.get(other_user_id)
            if not other_user:
                continue

            display_name = _user_display_name(other_user)
            last_text = (message.content or "").strip()
            if len(last_text) > 72:
                last_text = f"{last_text[:72]}..."

            conversations[other_user_id] = {
                "user_id": other_user_id,
                "username": other_user.username,
                "display_name": display_name,
                "last_message": last_text,
                "last_message_at": message.sent_at.isoformat(),
                "unread_count": unread_by_user.get(other_user_id, 0),
            }

        items = list(conversations.values())
        text_query = (query or "").strip().lower()
        if text_query:
            items = [
                item
                for item in items
                if text_query in (item.get("display_name") or "").lower()
                or text_query in (item.get("username") or "").lower()
                or text_query in (item.get("last_message") or "").lower()
            ]

        items.sort(key=lambda item: item.get("last_message_at") or "", reverse=True)
        return items

    @staticmethod
    def list_thread_messages(
        user_id: int,
        other_user_id: int,
        limit: int = 200,
        before_id: int | None = None,
    ) -> list[Message]:
        """Methode list_thread_messages : realise une partie de la logique de la classe."""
        other_user = User.query.get(other_user_id)
        if not other_user:
            raise NotFoundException("Discussion introuvable")

        max_limit = max(20, min(limit, 500))
        query = Message.query.filter(
            or_(
                (Message.sender_user_id == user_id) & (Message.recipient_user_id == other_user_id),
                (Message.sender_user_id == other_user_id) & (Message.recipient_user_id == user_id),
            )
        )

        if before_id and before_id > 0:
            query = query.filter(Message.id < before_id)

        messages = query.order_by(Message.sent_at.desc()).limit(max_limit).all()
        messages.reverse()
        return messages

    @staticmethod
    def mark_thread_as_read(user_id: int, other_user_id: int) -> int:
        """Methode mark_thread_as_read : realise une partie de la logique de la classe."""
        pending_messages = Message.query.filter(
            Message.sender_user_id == other_user_id,
            Message.recipient_user_id == user_id,
            Message.read_at.is_(None),
        ).all()
        if not pending_messages:
            return 0

        now = datetime.utcnow()
        for message in pending_messages:
            message.read_at = now
        db.session.commit()
        return len(pending_messages)

    @staticmethod
    def send_thread_message(sender_user_id: int, other_user_id: int, content: str, subject: str | None = None) -> Message:
        """Methode send_thread_message : realise une partie de la logique de la classe."""
        payload = {
            "recipient_user_id": other_user_id,
            "content": content,
            "subject": subject,
        }
        return EnterpriseService.send_message(sender_user_id, payload)

    @staticmethod
    def list_message_recipients(current_user_id: int) -> list[dict]:
        """Methode list_message_recipients : realise une partie de la logique de la classe."""
        current_user = User.query.get(current_user_id)
        current_employee_id = current_user.employee_id if current_user else None

        employees = (
            Employee.query.filter(
                or_(
                    Employee.status.is_(None),
                    Employee.status != EmployeeStatus.RESIGNED.value,
                )
            )
            .order_by(Employee.first_name.asc(), Employee.last_name.asc())
            .all()
        )

        recipients = []
        for employee in employees:
            if current_employee_id and employee.id == current_employee_id:
                continue

            user = employee.user
            recipients.append(
                {
                    "user_id": user.id if user else None,
                    "employee_id": employee.id,
                    "name": f"{employee.first_name} {employee.last_name}",
                    "matricule": employee.matricule,
                    "department": employee.department.name if employee.department else None,
                    "role": employee.role.name if employee.role else None,
                    "username": user.username if user else None,
                }
            )
        return recipients

    @staticmethod
    def send_message(sender_user_id: int, payload: dict) -> Message:
        """Methode send_message : realise une partie de la logique de la classe."""
        sender = User.query.get(sender_user_id)
        if not sender:
            raise NotFoundException("Expéditeur introuvable")

        recipient_user = None
        recipient_user_id = payload.get("recipient_user_id")
        if recipient_user_id:
            recipient_user = User.query.get(recipient_user_id)
        
        recipient_employee = None
        recipient_employee_id = payload.get("recipient_employee_id")
        if recipient_employee_id:
            recipient_employee = Employee.query.get(recipient_employee_id)
            if recipient_employee:
                recipient_user = recipient_employee.user

        if not recipient_user and recipient_employee:
            if not _is_active_employee_status(recipient_employee.status):
                raise ValidationException("Le destinataire n'est pas actif")

            generated_username = (recipient_employee.matricule or "").strip()
            if not generated_username:
                generated_username = f"agent{recipient_employee.id}"

            username_candidate = generated_username
            suffix = 1
            while User.query.filter_by(username=username_candidate).first():
                suffix += 1
                username_candidate = f"{generated_username}{suffix}"

            default_password = current_app.config.get("DEFAULT_AGENT_PASSWORD", "Agent@123")
            recipient_user = User(
                username=username_candidate,
                password_hash=hash_password(default_password),
                role_id=recipient_employee.role_id,
                employee_id=recipient_employee.id,
                must_change_password=True,
            )
            db.session.add(recipient_user)
            db.session.flush()

        if not recipient_user:
            raise ValidationException("Destinataire introuvable")

        if recipient_user.id == sender_user_id:
            raise ValidationException("Tu ne peux pas t'envoyer un message à toi-même")

        if recipient_user.employee and not _is_active_employee_status(recipient_user.employee.status):
            raise ValidationException("Le destinataire n'est pas actif")

        message = Message(
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user.id,
            subject=(payload.get("subject") or "").strip() or None,
            content=(payload.get("content") or "").strip(),
        )
        db.session.add(message)
        db.session.commit()
        return message

    @staticmethod
    def list_inbox(user_id: int, limit: int = 100) -> list[Message]:
        """Methode list_inbox : realise une partie de la logique de la classe."""
        return (
            Message.query.filter_by(recipient_user_id=user_id)
            .order_by(Message.sent_at.desc())
            .limit(max(1, min(limit, 300)))
            .all()
        )

    @staticmethod
    def list_sent_messages(user_id: int, limit: int = 100) -> list[Message]:
        """Methode list_sent_messages : realise une partie de la logique de la classe."""
        return (
            Message.query.filter_by(sender_user_id=user_id)
            .order_by(Message.sent_at.desc())
            .limit(max(1, min(limit, 300)))
            .all()
        )

    @staticmethod
    def count_unread_messages(user_id: int) -> int:
        """Methode count_unread_messages : realise une partie de la logique de la classe."""
        return Message.query.filter(
            Message.recipient_user_id == user_id,
            Message.read_at.is_(None),
        ).count()

    @staticmethod
    def mark_message_as_read(user_id: int, message_id: int) -> Message:
        """Methode mark_message_as_read : realise une partie de la logique de la classe."""
        message = Message.query.get(message_id)
        if not message:
            raise NotFoundException("Message introuvable")

        if message.recipient_user_id != user_id:
            raise ValidationException("Tu ne peux pas modifier ce message")

        if not message.read_at:
            message.read_at = datetime.utcnow()
            db.session.commit()

        return message

    @staticmethod
    def update_own_message(user_id: int, message_id: int, content: str) -> Message:
        """Methode update_own_message : realise une partie de la logique de la classe."""
        message = Message.query.get(message_id)
        if not message:
            raise NotFoundException("Message introuvable")

        if message.sender_user_id != user_id:
            raise ValidationException("Tu ne peux modifier que tes propres messages")

        if not EnterpriseService.can_edit_or_delete_message(user_id, message):
            raise ValidationException("Le délai de modification est dépassé")

        updated_content = (content or "").strip()
        if not updated_content:
            raise ValidationException("Le message ne peut pas être vide")

        message.content = updated_content
        message.edited_at = datetime.utcnow()
        db.session.commit()
        return message

    @staticmethod
    def delete_own_message(user_id: int, message_id: int) -> int:
        """Methode delete_own_message : realise une partie de la logique de la classe."""
        message = Message.query.get(message_id)
        if not message:
            raise NotFoundException("Message introuvable")

        if message.sender_user_id != user_id:
            raise ValidationException("Tu ne peux supprimer que tes propres messages")

        if not EnterpriseService.can_edit_or_delete_message(user_id, message):
            raise ValidationException("Le délai de suppression est dépassé")

        deleted_id = message.id
        db.session.delete(message)
        db.session.commit()
        return deleted_id

    @staticmethod
    def _generate_matricule(department_id: int | None, hire_date) -> str:
        """Methode _generate_matricule : realise une partie de la logique de la classe."""
        prefix = "GEN"
        if department_id:
            department = Department.query.get(department_id)
            if department and department.name:
                prefix = "".join([c for c in department.name.upper() if c.isalpha()])[:3] or "GEN"

        year = hire_date.year
        counter = 1
        while True:
            matricule = f"{prefix}-{year}-{counter:04d}"
            existing = Employee.query.filter_by(matricule=matricule).first()
            if not existing and not User.query.filter_by(username=matricule).first():
                return matricule
            counter += 1

    @staticmethod
    def list_employees() -> list[Employee]:
        """Methode list_employees : realise une partie de la logique de la classe."""
        return Employee.query.all()

    @staticmethod
    def get_employee(employee_id: int) -> Employee:
        """Methode get_employee : realise une partie de la logique de la classe."""
        employee = Employee.query.get(employee_id)
        if not employee:
            raise NotFoundException("Employé introuvable")
        return employee

    @staticmethod
    def create_employee(payload: dict) -> tuple[Employee, User, str]:
        """Methode create_employee : realise une partie de la logique de la classe."""
        if Employee.query.filter_by(email=payload["email"]).first():
            raise ValidationException("Email employé déjà existant")

        role = Role.query.get(payload["role_id"])
        if not role:
            raise NotFoundException("Rôle introuvable")

        matricule = EnterpriseService._generate_matricule(payload.get("department_id"), payload["hire_date"])
        payload["matricule"] = matricule

        employee = Employee(**payload)
        db.session.add(employee)

        default_password = current_app.config.get("DEFAULT_AGENT_PASSWORD", "Agent@123")
        db.session.flush()

        user = User(
            username=matricule,
            password_hash=hash_password(default_password),
            role_id=employee.role_id,
            employee_id=employee.id,
            must_change_password=True,
        )
        db.session.add(user)
        db.session.commit()
        return employee, user, default_password

    @staticmethod
    def update_employee(employee_id: int, payload: dict) -> Employee:
        """Methode update_employee : realise une partie de la logique de la classe."""
        employee = EnterpriseService.get_employee(employee_id)
        for key, value in payload.items():
            setattr(employee, key, value)

        if employee.user:
            employee.user.role_id = employee.role_id
        db.session.commit()
        return employee

    @staticmethod
    def delete_employee(employee_id: int) -> None:
        """Methode delete_employee : realise une partie de la logique de la classe."""
        employee = EnterpriseService.get_employee(employee_id)
        if employee.user:
            db.session.delete(employee.user)
        db.session.delete(employee)
        db.session.commit()

    @staticmethod
    def create_department(payload: dict) -> Department:
        """Methode create_department : realise une partie de la logique de la classe."""
        if Department.query.filter_by(name=payload["name"]).first():
            raise ValidationException("Département déjà existant")
        department = Department(**payload)
        db.session.add(department)
        db.session.commit()
        return department

    @staticmethod
    def list_departments() -> list[Department]:
        """Methode list_departments : realise une partie de la logique de la classe."""
        return Department.query.all()

    @staticmethod
    def update_department(department_id: int, payload: dict) -> Department:
        """Methode update_department : realise une partie de la logique de la classe."""
        department = Department.query.get(department_id)
        if not department:
            raise NotFoundException("Département introuvable")

        if payload.get("name"):
            existing = Department.query.filter(Department.name == payload["name"], Department.id != department_id).first()
            if existing:
                raise ValidationException("Département déjà existant")

        for key, value in payload.items():
            setattr(department, key, value)

        db.session.commit()
        return department

    @staticmethod
    def delete_department(department_id: int) -> None:
        """Methode delete_department : realise une partie de la logique de la classe."""
        department = Department.query.get(department_id)
        if not department:
            raise NotFoundException("Département introuvable")
        if department.employees:
            raise ValidationException("Impossible de supprimer un département contenant des employés")

        db.session.delete(department)
        db.session.commit()

    @staticmethod
    def assign_manager(department_id: int, manager_id: int) -> Department:
        """Methode assign_manager : realise une partie de la logique de la classe."""
        department = Department.query.get(department_id)
        if not department:
            raise NotFoundException("Département introuvable")
        manager = Employee.query.get(manager_id)
        if not manager:
            raise NotFoundException("Manager introuvable")
        department.manager_id = manager.id
        db.session.commit()
        return department

    @staticmethod
    def create_role(payload: dict) -> Role:
        """Methode create_role : realise une partie de la logique de la classe."""
        if Role.query.filter_by(name=payload["name"]).first():
            raise ValidationException("Rôle déjà existant")
        permission_names = payload.pop("permission_names", [])
        role = Role(**payload)
        if permission_names:
            permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
            if not permissions:
                raise ValidationException("Aucune permission valide trouvée")
            role.permissions = permissions
        db.session.add(role)
        db.session.commit()
        return role

    @staticmethod
    def list_roles() -> list[Role]:
        """Methode list_roles : realise une partie de la logique de la classe."""
        return Role.query.all()

    @staticmethod
    def list_permissions() -> list[Permission]:
        """Methode list_permissions : realise une partie de la logique de la classe."""
        return Permission.query.order_by(Permission.name.asc()).all()

    @staticmethod
    def assign_permissions(role_id: int, permission_names: list[str]) -> Role:
        """Methode assign_permissions : realise une partie de la logique de la classe."""
        role = Role.query.get(role_id)
        if not role:
            raise NotFoundException("Rôle introuvable")
        permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
        if not permissions:
            raise ValidationException("Aucune permission valide trouvée")
        role.permissions = permissions
        db.session.commit()
        return role

    @staticmethod
    def create_payroll(payload: dict) -> Payroll:
        """Methode create_payroll : realise une partie de la logique de la classe."""
        employee = Employee.query.get(payload["employee_id"])
        if not employee:
            raise NotFoundException("Employé introuvable")

        payroll_month = payload.pop("payroll_month", None)
        if payroll_month:
            try:
                target_year, target_month = [int(part) for part in payroll_month.split("-")]
                start = datetime(target_year, target_month, 1)
                last_day = monthrange(target_year, target_month)[1]
                end = datetime(target_year, target_month, last_day, 23, 59, 59)
            except (ValueError, TypeError):
                raise ValidationException("Format de mois invalide, attendu YYYY-MM")

            unjustified_absences = (
                Attendance.query.filter(
                    Attendance.employee_id == employee.id,
                    Attendance.is_absent.is_(True),
                    Attendance.check_in >= start,
                    Attendance.check_in <= end,
                ).count()
            )

            daily_penalty = payload["base_salary"] / 30
            payload["deductions"] = round(float(payload.get("deductions", 0)) + (daily_penalty * unjustified_absences), 2)

        net_salary = (
            payload["base_salary"]
            + payload.get("bonus", 0)
            + payload.get("overtime_hours", 0)
            - payload.get("deductions", 0)
            - payload.get("taxes", 0)
        )
        payload["net_salary"] = round(net_salary, 2)

        payroll = Payroll(**payload)
        db.session.add(payroll)
        db.session.commit()
        return payroll

    @staticmethod
    def list_payrolls() -> list[Payroll]:
        """Methode list_payrolls : realise une partie de la logique de la classe."""
        return Payroll.query.order_by(Payroll.paid_at.desc()).all()

    @staticmethod
    def update_payroll(payroll_id: int, payload: dict) -> Payroll:
        """Methode update_payroll : realise une partie de la logique de la classe."""
        payroll = Payroll.query.get(payroll_id)
        if not payroll:
            raise NotFoundException("Paie introuvable")

        for key, value in payload.items():
            setattr(payroll, key, value)

        payroll.net_salary = round(
            float(payroll.base_salary)
            + float(payroll.bonus or 0)
            + float(payroll.overtime_hours or 0)
            - float(payroll.deductions or 0)
            - float(payroll.taxes or 0),
            2,
        )
        db.session.commit()
        return payroll

    @staticmethod
    def delete_payroll(payroll_id: int) -> None:
        """Methode delete_payroll : realise une partie de la logique de la classe."""
        payroll = Payroll.query.get(payroll_id)
        if not payroll:
            raise NotFoundException("Paie introuvable")
        db.session.delete(payroll)
        db.session.commit()

    @staticmethod
    def create_attendance(payload: dict) -> Attendance:
        """Methode create_attendance : realise une partie de la logique de la classe."""
        employee = Employee.query.get(payload["employee_id"])
        if not employee:
            raise NotFoundException("Employé introuvable")
        attendance = Attendance(**payload)
        db.session.add(attendance)
        db.session.commit()
        return attendance

    @staticmethod
    def checkout_attendance(attendance_id: int, check_out: datetime) -> Attendance:
        """Methode checkout_attendance : realise une partie de la logique de la classe."""
        attendance = Attendance.query.get(attendance_id)
        if not attendance:
            raise NotFoundException("Pointage introuvable")
        attendance.check_out = check_out
        duration = (attendance.check_out - attendance.check_in).total_seconds() / 3600
        attendance.worked_hours = round(max(duration, 0), 2)
        db.session.commit()
        return attendance

    @staticmethod
    def checkout_attendance_by_employee(employee_id: int, check_out: datetime) -> Attendance:
        """Methode checkout_attendance_by_employee : realise une partie de la logique de la classe."""
        attendance = (
            Attendance.query.filter_by(employee_id=employee_id, check_out=None)
            .order_by(Attendance.check_in.desc())
            .first()
        )
        if not attendance:
            raise NotFoundException("Aucun pointage d'entrée ouvert pour cet employé")

        return EnterpriseService.checkout_attendance(attendance.id, check_out)

    @staticmethod
    def list_attendance() -> list[Attendance]:
        """Methode list_attendance : realise une partie de la logique de la classe."""
        return Attendance.query.order_by(Attendance.id.desc()).all()

    @staticmethod
    def update_attendance(attendance_id: int, payload: dict) -> Attendance:
        """Methode update_attendance : realise une partie de la logique de la classe."""
        attendance = Attendance.query.get(attendance_id)
        if not attendance:
            raise NotFoundException("Pointage introuvable")

        for key, value in payload.items():
            setattr(attendance, key, value)

        if attendance.check_out and attendance.check_in:
            duration = (attendance.check_out - attendance.check_in).total_seconds() / 3600
            attendance.worked_hours = round(max(duration, 0), 2)

        db.session.commit()
        return attendance

    @staticmethod
    def delete_attendance(attendance_id: int) -> None:
        """Methode delete_attendance : realise une partie de la logique de la classe."""
        attendance = Attendance.query.get(attendance_id)
        if not attendance:
            raise NotFoundException("Pointage introuvable")
        db.session.delete(attendance)
        db.session.commit()

    @staticmethod
    def monthly_attendance_summary(month: str) -> list[dict]:
        """Methode monthly_attendance_summary : realise une partie de la logique de la classe."""
        try:
            year, month_value = [int(part) for part in month.split("-")]
            start = datetime(year, month_value, 1)
            end = datetime(year, month_value, monthrange(year, month_value)[1], 23, 59, 59)
        except (ValueError, TypeError):
            raise ValidationException("Format de mois invalide, attendu YYYY-MM")

        employees = Employee.query.order_by(Employee.first_name.asc(), Employee.last_name.asc()).all()
        summaries: list[dict] = []
        for employee in employees:
            records = Attendance.query.filter(
                Attendance.employee_id == employee.id,
                Attendance.check_in >= start,
                Attendance.check_in <= end,
            ).all()

            presents = sum(1 for record in records if not record.is_absent)
            absences = sum(1 for record in records if record.is_absent)
            summaries.append(
                {
                    "employee_id": employee.id,
                    "employee_name": f"{employee.first_name} {employee.last_name}",
                    "month": month,
                    "presence_days": presents,
                    "absence_days": absences,
                    "unjustified_absence_days": absences,
                }
            )

        return summaries

    @staticmethod
    def create_leave(payload: dict) -> Leave:
        """Methode create_leave : realise une partie de la logique de la classe."""
        employee = Employee.query.get(payload["employee_id"])
        if not employee:
            raise NotFoundException("Employé introuvable")
        leave = Leave(**payload)
        db.session.add(leave)
        db.session.commit()
        return leave

    @staticmethod
    def approve_leave(leave_id: int, status: str) -> Leave:
        """Methode approve_leave : realise une partie de la logique de la classe."""
        leave = Leave.query.get(leave_id)
        if not leave:
            raise NotFoundException("Congé introuvable")
    def approve_leave(leave_id: int, status: str, decision_comment: str | None = None) -> Leave:
        """Methode approve_leave : realise une partie de la logique de la classe."""
        leave = Leave.query.get(leave_id)
        if not leave:
            raise NotFoundException("Congé introuvable")

        if status not in {"En attente", "Approuvé", "Rejeté"}:
            raise ValidationException("Statut invalide")

        leave.status = status
        # store RH justification or comment when provided (e.g., on rejection)
        if decision_comment is not None:
            leave.decision_comment = decision_comment

        db.session.commit()
        return leave

    @staticmethod
    def list_leaves(employee_id: int | None = None) -> list[Leave]:
        """Methode list_leaves : realise une partie de la logique de la classe."""
        query = Leave.query.order_by(Leave.id.desc())
        if employee_id is not None:
            query = query.filter(Leave.employee_id == employee_id)
        return query.all()

    @staticmethod
    def update_leave(leave_id: int, payload: dict) -> Leave:
        """Methode update_leave : realise une partie de la logique de la classe."""
        leave = Leave.query.get(leave_id)
        if not leave:
            raise NotFoundException("Congé introuvable")
        for key, value in payload.items():
            setattr(leave, key, value)
        db.session.commit()
        return leave

    @staticmethod
    def delete_leave(leave_id: int) -> None:
        """Methode delete_leave : realise une partie de la logique de la classe."""
        leave = Leave.query.get(leave_id)
        if not leave:
            raise NotFoundException("Congé introuvable")
        db.session.delete(leave)
        db.session.commit()

    @staticmethod
    def create_contract(payload: dict) -> Contract:
        """Methode create_contract : realise une partie de la logique de la classe."""
        employee = Employee.query.get(payload["employee_id"])
        if not employee:
            raise NotFoundException("Employé introuvable")
        contract = Contract(**payload)
        db.session.add(contract)
        db.session.commit()
        return contract

    @staticmethod
    def list_contracts() -> list[Contract]:
        """Methode list_contracts : realise une partie de la logique de la classe."""
        return Contract.query.order_by(Contract.id.desc()).all()

    @staticmethod
    def update_contract(contract_id: int, payload: dict) -> Contract:
        """Methode update_contract : realise une partie de la logique de la classe."""
        contract = Contract.query.get(contract_id)
        if not contract:
            raise NotFoundException("Contrat introuvable")
        for key, value in payload.items():
            setattr(contract, key, value)
        db.session.commit()
        return contract

    @staticmethod
    def delete_contract(contract_id: int) -> None:
        """Methode delete_contract : realise une partie de la logique de la classe."""
        contract = Contract.query.get(contract_id)
        if not contract:
            raise NotFoundException("Contrat introuvable")
        db.session.delete(contract)
        db.session.commit()

    @staticmethod
    def payroll_statistics() -> dict:
        """Methode payroll_statistics : realise une partie de la logique de la classe."""
        payrolls = Payroll.query.all()
        df = pd.DataFrame(
            [
                {
                    "employee_id": p.employee_id,
                    "net_salary": p.net_salary,
                    "department": p.employee.department.name if p.employee.department else "Non assigné",
                }
                for p in payrolls
            ]
        )

        if df.empty:
            return {
                "total_payroll": 0,
                "average_salary": 0,
                "employees_by_department": {},
                "absence_rate": 0,
            }

        attendance = Attendance.query.all()
        attendance_df = pd.DataFrame(
            [{"is_absent": a.is_absent} for a in attendance]
        )
        absence_rate = 0
        if not attendance_df.empty:
            absence_rate = round(float(attendance_df["is_absent"].mean() * 100), 2)

        employees_by_department = (
            df.groupby("department")["employee_id"].nunique().to_dict()
        )

        return {
            "total_payroll": round(float(df["net_salary"].sum()), 2),
            "average_salary": round(float(df["net_salary"].mean()), 2),
            "employees_by_department": employees_by_department,
            "absence_rate": absence_rate,
        }

    @staticmethod
    def accounting_statistics() -> dict:
        """Methode accounting_statistics : realise une partie de la logique de la classe."""
        payrolls = Payroll.query.order_by(Payroll.paid_at.asc()).all()

        if not payrolls:
            return {
                "totals": {
                    "gross_payroll": 0,
                    "net_payroll": 0,
                    "taxes": 0,
                    "deductions": 0,
                    "bonuses": 0,
                    "overtime_hours": 0,
                    "records": 0,
                },
                "monthly": {
                    "labels": [],
                    "gross": [],
                    "net": [],
                    "taxes": [],
                    "deductions": [],
                    "bonuses": [],
                },
                "department_net": {
                    "labels": [],
                    "values": [],
                },
                "cost_structure": {
                    "labels": ["Salaires nets", "Impôts", "Déductions", "Primes"],
                    "values": [0, 0, 0, 0],
                },
            }

        monthly_map: dict[str, dict[str, float]] = {}
        department_net: dict[str, float] = {}

        total_gross = 0.0
        total_net = 0.0
        total_taxes = 0.0
        total_deductions = 0.0
        total_bonuses = 0.0
        total_overtime = 0.0

        for payroll in payrolls:
            month_key = payroll.paid_at.strftime("%Y-%m")
            gross_value = float(payroll.base_salary or 0) + float(payroll.bonus or 0) + float(payroll.overtime_hours or 0)
            net_value = float(payroll.net_salary or 0)
            taxes_value = float(payroll.taxes or 0)
            deductions_value = float(payroll.deductions or 0)
            bonus_value = float(payroll.bonus or 0)
            overtime_value = float(payroll.overtime_hours or 0)

            month_item = monthly_map.setdefault(
                month_key,
                {
                    "gross": 0.0,
                    "net": 0.0,
                    "taxes": 0.0,
                    "deductions": 0.0,
                    "bonuses": 0.0,
                },
            )
            month_item["gross"] += gross_value
            month_item["net"] += net_value
            month_item["taxes"] += taxes_value
            month_item["deductions"] += deductions_value
            month_item["bonuses"] += bonus_value

            department_name = payroll.employee.department.name if payroll.employee and payroll.employee.department else "Non assigné"
            department_net[department_name] = department_net.get(department_name, 0.0) + net_value

            total_gross += gross_value
            total_net += net_value
            total_taxes += taxes_value
            total_deductions += deductions_value
            total_bonuses += bonus_value
            total_overtime += overtime_value

        labels = sorted(monthly_map.keys())

        sorted_departments = sorted(department_net.items(), key=lambda item: item[1], reverse=True)

        return {
            "totals": {
                "gross_payroll": round(total_gross, 2),
                "net_payroll": round(total_net, 2),
                "taxes": round(total_taxes, 2),
                "deductions": round(total_deductions, 2),
                "bonuses": round(total_bonuses, 2),
                "overtime_hours": round(total_overtime, 2),
                "records": len(payrolls),
            },
            "monthly": {
                "labels": labels,
                "gross": [round(monthly_map[label]["gross"], 2) for label in labels],
                "net": [round(monthly_map[label]["net"], 2) for label in labels],
                "taxes": [round(monthly_map[label]["taxes"], 2) for label in labels],
                "deductions": [round(monthly_map[label]["deductions"], 2) for label in labels],
                "bonuses": [round(monthly_map[label]["bonuses"], 2) for label in labels],
            },
            "department_net": {
                "labels": [item[0] for item in sorted_departments],
                "values": [round(item[1], 2) for item in sorted_departments],
            },
            "cost_structure": {
                "labels": ["Salaires nets", "Impôts", "Déductions", "Primes"],
                "values": [
                    round(total_net, 2),
                    round(total_taxes, 2),
                    round(total_deductions, 2),
                    round(total_bonuses, 2),
                ],
            },
        }
