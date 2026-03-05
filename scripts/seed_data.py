"""
Rôle du fichier:
Insère des données de démonstration dans la base pour tester rapidement les fonctionnalités métier.
"""

from datetime import date, datetime, timedelta
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.extensions import db
from app.models import Attendance, Contract, Department, Employee, Leave, Payroll, Role, User
from app.services.auth_service import seed_rbac
from app.utils.security import hash_password


def seed_departments() -> dict[str, Department]:
    """Fonction seed_departments : execute une partie de la logique applicative."""
    departments_payload = [
        {"name": "IT", "budget": 250000},
        {"name": "RH", "budget": 150000},
        {"name": "Finance", "budget": 200000},
        {"name": "Marketing", "budget": 120000},
    ]

    result: dict[str, Department] = {}
    for payload in departments_payload:
        dep = Department.query.filter_by(name=payload["name"]).first()
        if not dep:
            dep = Department(**payload)
            db.session.add(dep)
            db.session.flush()
        result[payload["name"]] = dep

    db.session.commit()
    return result


def seed_employees(departments: dict[str, Department], roles: dict[str, Role]) -> dict[str, Employee]:
    """Fonction seed_employees : execute une partie de la logique applicative."""
    employees_payload = [
        {
            "first_name": "Kevin",
            "last_name": "Belo",
            "matricule": "IT-2024-0001",
            "photo_url": None,
            "email": "kevin.belo@entreprise.com",
            "phone": "+243900000001",
            "address": "Kinshasa, Gombe",
            "hire_date": date(2024, 1, 10),
            "status": "Actif",
            "department": "IT",
            "role": "SuperAdmin",
        },
        {
            "first_name": "Alice",
            "last_name": "Mwamba",
            "matricule": "RH-2024-0001",
            "photo_url": None,
            "email": "alice.mwamba@entreprise.com",
            "phone": "+243900000002",
            "address": "Kinshasa, Limete",
            "hire_date": date(2024, 3, 2),
            "status": "Actif",
            "department": "RH",
            "role": "Admin RH",
        },
        {
            "first_name": "Jean",
            "last_name": "Kasongo",
            "matricule": "IT-2023-0001",
            "photo_url": None,
            "email": "jean.kasongo@entreprise.com",
            "phone": "+243900000003",
            "address": "Kinshasa, Kintambo",
            "hire_date": date(2023, 9, 1),
            "status": "Actif",
            "department": "IT",
            "role": "Manager",
        },
        {
            "first_name": "Sarah",
            "last_name": "Ilunga",
            "matricule": "IT-2025-0001",
            "photo_url": None,
            "email": "sarah.ilunga@entreprise.com",
            "phone": "+243900000004",
            "address": "Kinshasa, Ngaliema",
            "hire_date": date(2025, 1, 15),
            "status": "Actif",
            "department": "IT",
            "role": "Employé",
        },
    ]

    result: dict[str, Employee] = {}
    for payload in employees_payload:
        employee = Employee.query.filter_by(email=payload["email"]).first()
        if not employee:
            employee = Employee(
                first_name=payload["first_name"],
                last_name=payload["last_name"],
                matricule=payload["matricule"],
                photo_url=payload["photo_url"],
                email=payload["email"],
                phone=payload["phone"],
                address=payload["address"],
                hire_date=payload["hire_date"],
                status=payload["status"],
                department_id=departments[payload["department"]].id,
                role_id=roles[payload["role"]].id,
            )
            db.session.add(employee)
            db.session.flush()

        result[payload["email"]] = employee

    db.session.commit()
    return result


def seed_users(employees: dict[str, Employee]) -> None:
    """Fonction seed_users : execute une partie de la logique applicative."""
    default_password = "Agent@123"

    for employee in employees.values():
        username = employee.matricule or f"EMP-{employee.id:04d}"
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(
                username=username,
                password_hash=hash_password(default_password),
                role_id=employee.role_id,
                employee_id=employee.id,
                must_change_password=True,
            )
            db.session.add(user)

    superadmin = User.query.filter_by(username="superadmin").first()
    if not superadmin:
        employee = Employee.query.filter_by(email="kevin.belo@entreprise.com").first()
        superadmin = User(
            username="superadmin",
            password_hash=hash_password("superadmin123"),
            role_id=employee.role_id if employee else Role.query.filter_by(name="SuperAdmin").first().id,
            employee_id=employee.id if employee else None,
            must_change_password=False,
        )
        db.session.add(superadmin)

    db.session.commit()


def seed_payrolls(employees: dict[str, Employee]) -> None:
    """Fonction seed_payrolls : execute une partie de la logique applicative."""
    payroll_payload = [
        {
            "email": "kevin.belo@entreprise.com",
            "base_salary": 2200,
            "bonus": 200,
            "overtime_hours": 80,
            "deductions": 50,
            "taxes": 200,
        },
        {
            "email": "alice.mwamba@entreprise.com",
            "base_salary": 1800,
            "bonus": 100,
            "overtime_hours": 30,
            "deductions": 40,
            "taxes": 160,
        },
        {
            "email": "jean.kasongo@entreprise.com",
            "base_salary": 2000,
            "bonus": 150,
            "overtime_hours": 40,
            "deductions": 60,
            "taxes": 180,
        },
        {
            "email": "sarah.ilunga@entreprise.com",
            "base_salary": 1200,
            "bonus": 50,
            "overtime_hours": 20,
            "deductions": 20,
            "taxes": 90,
        },
    ]

    for payload in payroll_payload:
        employee = employees[payload["email"]]
        existing = Payroll.query.filter_by(employee_id=employee.id).first()
        if existing:
            continue

        net_salary = (
            payload["base_salary"]
            + payload["bonus"]
            + payload["overtime_hours"]
            - payload["deductions"]
            - payload["taxes"]
        )

        payroll = Payroll(
            employee_id=employee.id,
            base_salary=payload["base_salary"],
            bonus=payload["bonus"],
            overtime_hours=payload["overtime_hours"],
            deductions=payload["deductions"],
            taxes=payload["taxes"],
            net_salary=round(net_salary, 2),
        )
        db.session.add(payroll)

    db.session.commit()


def seed_attendances(employees: dict[str, Employee]) -> None:
    """Fonction seed_attendances : execute une partie de la logique applicative."""
    for employee in employees.values():
        if Attendance.query.filter_by(employee_id=employee.id).first():
            continue

        check_in = datetime.now().replace(hour=8, minute=15, second=0, microsecond=0)
        check_out = check_in + timedelta(hours=8, minutes=20)
        worked_hours = round((check_out - check_in).total_seconds() / 3600, 2)

        attendance = Attendance(
            employee_id=employee.id,
            check_in=check_in,
            check_out=check_out,
            worked_hours=worked_hours,
            late_minutes=15,
            is_absent=False,
        )
        db.session.add(attendance)

    db.session.commit()


def seed_leaves_and_contracts(employees: dict[str, Employee]) -> None:
    """Fonction seed_leaves_and_contracts : execute une partie de la logique applicative."""
    for employee in employees.values():
        if not Leave.query.filter_by(employee_id=employee.id).first():
            leave = Leave(
                employee_id=employee.id,
                start_date=date(2026, 3, 10),
                end_date=date(2026, 3, 14),
                reason="Congé annuel",
                status="Approuvé" if employee.first_name in {"Kevin", "Jean"} else "En attente",
            )
            db.session.add(leave)

        if not Contract.query.filter_by(employee_id=employee.id).first():
            contract = Contract(
                employee_id=employee.id,
                contract_type="CDI",
                start_date=employee.hire_date,
                end_date=None,
                contractual_salary=1500,
                document_path=None,
            )
            db.session.add(contract)

    db.session.commit()


def assign_it_manager(departments: dict[str, Department], employees: dict[str, Employee]) -> None:
    """Fonction assign_it_manager : execute une partie de la logique applicative."""
    it = departments["IT"]
    manager = employees["jean.kasongo@entreprise.com"]
    it.manager_id = manager.id
    db.session.commit()


def run_seed() -> None:
    """Fonction run_seed : execute une partie de la logique applicative."""
    app = create_app()
    with app.app_context():
        db.create_all()
        seed_rbac()

        roles = {role.name: role for role in Role.query.all()}
        departments = seed_departments()
        employees = seed_employees(departments, roles)
        seed_users(employees)
        seed_payrolls(employees)
        seed_attendances(employees)
        seed_leaves_and_contracts(employees)
        assign_it_manager(departments, employees)

        print("Seed terminé avec succès.")
        print("Utilisateurs de test:")
        print("- superadmin / superadmin123")
        print("- comptes agents: username = matricule, mot de passe par défaut = Agent@123")


if __name__ == "__main__":
    run_seed()
