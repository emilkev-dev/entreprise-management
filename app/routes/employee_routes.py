"""
Rôle du fichier:
Expose les endpoints CRUD des employés.
"""

from pydantic import ValidationError

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from app.schemas.payloads import EmployeeCreateSchema, EmployeeUpdateSchema
from app.services.enterprise_service import EnterpriseService
from app.utils.activity_logger import log_activity
from app.utils.rbac import permission_required
from app.utils.serializers import employee_to_dict


employee_bp = Blueprint("employees", __name__)


@employee_bp.get("")
@jwt_required()
@permission_required("Voir employés")
def list_employees():
    """Liste tous les employés sérialisés pour le frontend."""
    employees = EnterpriseService.list_employees()
    return jsonify([employee_to_dict(emp) for emp in employees])


@employee_bp.post("")
@jwt_required()
@permission_required("Modifier employés")
def create_employee():
    """Crée un employé et son compte agent auto-généré."""
    try:
        payload = EmployeeCreateSchema.model_validate(request.get_json() or {})
        employee, user, default_password = EnterpriseService.create_employee(payload.model_dump())
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Création employé #{employee.id}")
        return (
            jsonify(
                {
                    **employee_to_dict(employee),
                    "generated_account": {
                        "username": user.username,
                        "must_change_password": user.must_change_password,
                        "default_password": default_password,
                    },
                }
            ),
            201,
        )
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@employee_bp.put("/<int:employee_id>")
@jwt_required()
@permission_required("Modifier employés")
def update_employee(employee_id: int):
    """Met à jour les informations d'un employé existant."""
    try:
        payload = EmployeeUpdateSchema.model_validate(request.get_json() or {})
        employee = EnterpriseService.update_employee(employee_id, payload.model_dump(exclude_none=True))
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Modification employé #{employee.id}")
        return jsonify(employee_to_dict(employee))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@employee_bp.delete("/<int:employee_id>")
@jwt_required()
@permission_required("Modifier employés")
def delete_employee(employee_id: int):
    """Supprime un employé (et son compte lié via service)."""
    EnterpriseService.delete_employee(employee_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Suppression employé #{employee_id}")
    return jsonify({"message": "Employé supprimé"})
