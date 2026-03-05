"""
Rôle du fichier:
Expose les endpoints de pointage et de suivi des présences.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from pydantic import ValidationError

from app.schemas.payloads import AttendanceCheckInSchema, AttendanceCheckOutSchema, AttendanceCheckoutByEmployeeSchema, AttendanceUpdateSchema
from app.services.enterprise_service import EnterpriseService
from app.utils.activity_logger import log_activity
from app.utils.rbac import permission_required
from app.utils.serializers import attendance_to_dict


attendance_bp = Blueprint("attendances", __name__)


@attendance_bp.get("")
@jwt_required()
@permission_required("Voir employés")
def list_attendances():
    """Retourne les pointages enregistrés."""
    attendances = EnterpriseService.list_attendance()
    return jsonify([attendance_to_dict(a) for a in attendances])


@attendance_bp.post("/checkin")
@jwt_required()
@permission_required("Voir employés")
def checkin():
    """Enregistre un pointage d'entrée."""
    try:
        payload = AttendanceCheckInSchema.model_validate(request.get_json() or {})
        attendance = EnterpriseService.create_attendance(payload.model_dump())
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Check-in employé #{attendance.employee_id}")
        return jsonify(attendance_to_dict(attendance)), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@attendance_bp.post("/checkout")
@jwt_required()
@permission_required("Voir employés")
def checkout():
    """Enregistre un pointage de sortie à partir d'un attendance_id."""
    try:
        payload = AttendanceCheckOutSchema.model_validate(request.get_json() or {})
        attendance = EnterpriseService.checkout_attendance(payload.attendance_id, payload.check_out)
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Check-out employé #{attendance.employee_id}")
        return jsonify(attendance_to_dict(attendance))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@attendance_bp.post("/checkout-employee")
@jwt_required()
@permission_required("Voir employés")
def checkout_employee():
    """Enregistre un pointage de sortie via employee_id."""
    try:
        payload = AttendanceCheckoutByEmployeeSchema.model_validate(request.get_json() or {})
        attendance = EnterpriseService.checkout_attendance_by_employee(payload.employee_id, payload.check_out)
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Check-out employé #{attendance.employee_id}")
        return jsonify(attendance_to_dict(attendance))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@attendance_bp.get("/summary/monthly")
@jwt_required()
@permission_required("Voir employés")
def monthly_summary():
    """Retourne le résumé mensuel des présences/absences par employé."""
    month = (request.args.get("month") or "").strip()
    if not month:
        return jsonify({"error": "Paramètre 'month' requis (YYYY-MM)"}), 400

    summary = EnterpriseService.monthly_attendance_summary(month)
    return jsonify(summary)


@attendance_bp.put("/<int:attendance_id>")
@jwt_required()
@permission_required("Voir employés")
def update_attendance(attendance_id: int):
    """Met à jour un enregistrement de présence existant."""
    try:
        payload = AttendanceUpdateSchema.model_validate(request.get_json() or {})
        attendance = EnterpriseService.update_attendance(attendance_id, payload.model_dump(exclude_none=True))
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Modification pointage #{attendance.id}")
        return jsonify(attendance_to_dict(attendance))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@attendance_bp.delete("/<int:attendance_id>")
@jwt_required()
@permission_required("Voir employés")
def delete_attendance(attendance_id: int):
    """Supprime un enregistrement de présence."""
    EnterpriseService.delete_attendance(attendance_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Suppression pointage #{attendance_id}")
    return jsonify({"message": "Pointage supprimé"})
