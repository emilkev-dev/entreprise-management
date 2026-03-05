"""
Rôle du fichier:
Expose les endpoints de gestion des rôles et de leurs permissions.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from pydantic import ValidationError

from app.schemas.payloads import PermissionAssignSchema, RoleCreateSchema
from app.services.enterprise_service import EnterpriseService
from app.utils.activity_logger import log_activity
from app.utils.rbac import permission_required
from app.utils.serializers import role_to_dict


role_bp = Blueprint("roles", __name__)


@role_bp.get("")
@jwt_required()
@permission_required("Voir employés")
def list_roles():
    """Retourne tous les rôles et leurs permissions associées."""
    roles = EnterpriseService.list_roles()
    return jsonify([role_to_dict(role) for role in roles])


@role_bp.get("/permissions")
@jwt_required()
@permission_required("Voir employés")
def list_permissions():
    """Retourne la liste de toutes les permissions disponibles."""
    permissions = EnterpriseService.list_permissions()
    return jsonify([permission.name for permission in permissions])


@role_bp.post("")
@jwt_required()
@permission_required("Modifier employés")
def create_role():
    """Crée un nouveau rôle et ses permissions initiales."""
    try:
        payload = RoleCreateSchema.model_validate(request.get_json() or {})
        role = EnterpriseService.create_role(payload.model_dump())
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Création rôle #{role.id}")
        return jsonify(role_to_dict(role)), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@role_bp.patch("/<int:role_id>/permissions")
@jwt_required()
@permission_required("Modifier employés")
def assign_permissions(role_id: int):
    """Remplace les permissions d'un rôle existant."""
    try:
        payload = PermissionAssignSchema.model_validate(request.get_json() or {})
        role = EnterpriseService.assign_permissions(role_id, payload.permission_names)
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Mise à jour permissions rôle #{role.id}")
        return jsonify(role_to_dict(role))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422
