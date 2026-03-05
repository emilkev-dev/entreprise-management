"""
Rôle du fichier:
Expose les modèles de données SQLAlchemy pour simplifier les imports dans le reste du projet.
"""

from app.models.db_models import (
    ActivityLog,
    Attendance,
    Contract,
    ContractType,
    Department,
    Employee,
    EmployeeStatus,
    Leave,
    Message,
    Payroll,
    Permission,
    Role,
    User,
)

__all__ = [
    "User",
    "Role",
    "Permission",
    "Department",
    "Employee",
    "Message",
    "Payroll",
    "Attendance",
    "Leave",
    "Contract",
    "ActivityLog",
    "EmployeeStatus",
    "ContractType",
]
