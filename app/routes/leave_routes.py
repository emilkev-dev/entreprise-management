"""
Rôle du fichier:
Expose les endpoints de gestion des congés (création, consultation, validation, modification, suppression).
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required, get_jwt_identity
from pydantic import ValidationError

from app.schemas.payloads import LeaveApprovalSchema, LeaveCreateSchema, LeaveUpdateSchema
from app.models import User, Leave
from app.services.enterprise_service import EnterpriseService
from app.utils.activity_logger import log_activity
from app.utils.rbac import permission_required
from app.utils.serializers import leave_to_dict


leave_bp = Blueprint("leaves", __name__)


@leave_bp.get("")
@jwt_required()
def list_leaves():
    """Liste les congés visibles selon les permissions de l'utilisateur connecté."""
    claims = get_jwt()
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    # HR and roles with 'Valider congés' see all leaves
    if "Valider congés" in (claims.get("permissions") or []):
        leaves = EnterpriseService.list_leaves()
    else:
        # regular employees see only their own leave requests
        employee_id = user.employee_id if user else None
        leaves = EnterpriseService.list_leaves(employee_id=employee_id)

    return jsonify([leave_to_dict(leave) for leave in leaves])


@leave_bp.post("")
@jwt_required()
def create_leave():
    """Crée une nouvelle demande de congé."""
    try:
        payload = LeaveCreateSchema.model_validate(request.get_json() or {})
        leave = EnterpriseService.create_leave(payload.model_dump())
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Demande congé #{leave.id}")
        return jsonify(leave_to_dict(leave)), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@leave_bp.patch("/<int:leave_id>/approval")
@jwt_required()
@permission_required("Valider congés")
def approve_leave(leave_id: int):
    """Valide ou rejette un congé (réservé aux profils autorisés)."""
    try:
        payload = LeaveApprovalSchema.model_validate(request.get_json() or {})
        leave = EnterpriseService.approve_leave(leave_id, payload.status, payload.decision_comment)
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Validation congé #{leave.id}: {payload.status}")
        return jsonify(leave_to_dict(leave))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@leave_bp.put("/<int:leave_id>")
@jwt_required()
def update_leave(leave_id: int):
    """Met à jour un congé si l'utilisateur est propriétaire ou validateur RH."""
    try:
        payload = LeaveUpdateSchema.model_validate(request.get_json() or {})
        # allow owner or HR (Valider congés) to update
        claims = get_jwt()
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        leave = Leave.query.get(leave_id)
        if not leave:
            return jsonify({"error": "Congé introuvable"}), 404

        if not ("Valider congés" in (claims.get("permissions") or []) or (user and user.employee_id == leave.employee_id)):
            return jsonify({"error": "Accès refusé"}), 403

        leave = EnterpriseService.update_leave(leave_id, payload.model_dump(exclude_none=True))
        log_activity(claims.get("username", "unknown"), f"Modification congé #{leave.id}")
        return jsonify(leave_to_dict(leave))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@leave_bp.delete("/<int:leave_id>")
@jwt_required()
def delete_leave(leave_id: int):
    """Supprime un congé si l'utilisateur est propriétaire ou validateur RH."""
    claims = get_jwt()
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    leave = Leave.query.get(leave_id)
    if not leave:
        return jsonify({"error": "Congé introuvable"}), 404

    if not ("Valider congés" in (claims.get("permissions") or []) or (user and user.employee_id == leave.employee_id)):
        return jsonify({"error": "Accès refusé"}), 403

    EnterpriseService.delete_leave(leave_id)
    log_activity(claims.get("username", "unknown"), f"Suppression congé #{leave_id}")
    return jsonify({"message": "Congé supprimé"})
