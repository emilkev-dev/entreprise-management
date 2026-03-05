"""
Rôle du fichier:
Expose les endpoints CRUD des départements et la gestion de leur responsable.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from pydantic import ValidationError

from app.schemas.payloads import DepartmentCreateSchema, DepartmentUpdateSchema
from app.services.enterprise_service import EnterpriseService
from app.utils.activity_logger import log_activity
from app.utils.rbac import permission_required
from app.utils.serializers import department_to_dict


department_bp = Blueprint("departments", __name__)


@department_bp.get("")
@jwt_required()
@permission_required("Voir employés")
def list_departments():
    """Retourne la liste des départements avec leurs informations utiles."""
    departments = EnterpriseService.list_departments()
    return jsonify([department_to_dict(dep) for dep in departments])


@department_bp.post("")
@jwt_required()
@permission_required("Modifier employés")
def create_department():
    """Crée un département à partir des données validées."""
    try:
        payload = DepartmentCreateSchema.model_validate(request.get_json() or {})
        department = EnterpriseService.create_department(payload.model_dump())
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Création département #{department.id}")
        return jsonify(department_to_dict(department)), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@department_bp.put("/<int:department_id>")
@jwt_required()
@permission_required("Modifier employés")
def update_department(department_id: int):
    """Modifie un département existant."""
    try:
        payload = DepartmentUpdateSchema.model_validate(request.get_json() or {})
        department = EnterpriseService.update_department(department_id, payload.model_dump(exclude_none=True))
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Modification département #{department.id}")
        return jsonify(department_to_dict(department))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@department_bp.delete("/<int:department_id>")
@jwt_required()
@permission_required("Modifier employés")
def delete_department(department_id: int):
    """Supprime un département (si les règles métier le permettent)."""
    EnterpriseService.delete_department(department_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Suppression département #{department_id}")
    return jsonify({"message": "Département supprimé"})


@department_bp.patch("/<int:department_id>/manager/<int:manager_id>")
@jwt_required()
@permission_required("Modifier employés")
def assign_manager(department_id: int, manager_id: int):
    """Affecte un manager à un département."""
    department = EnterpriseService.assign_manager(department_id, manager_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Assignation manager {manager_id} -> département {department_id}")
    return jsonify(department_to_dict(department))
