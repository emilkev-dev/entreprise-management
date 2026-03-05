"""
Rôle du fichier:
Expose les endpoints de gestion de la paie et des bulletins associés.
"""

import os

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import get_jwt, jwt_required
from pydantic import ValidationError
from flask import request

from app.models import Payroll
from app.schemas.payloads import PayrollCreateSchema, PayrollUpdateSchema
from app.services.enterprise_service import EnterpriseService
from app.utils.activity_logger import log_activity
from app.utils.pdf_utils import generate_payslip_pdf
from app.utils.rbac import permission_required
from app.utils.serializers import payroll_to_dict


payroll_bp = Blueprint("payrolls", __name__)


@payroll_bp.get("")
@jwt_required()
@permission_required("Voir salaires")
def list_payrolls():
    """Retourne toutes les fiches de paie."""
    payrolls = EnterpriseService.list_payrolls()
    return jsonify([payroll_to_dict(payroll) for payroll in payrolls])


@payroll_bp.post("")
@jwt_required()
@permission_required("Voir salaires")
def create_payroll():
    """Crée une fiche de paie à partir des données reçues."""
    try:
        payload = PayrollCreateSchema.model_validate(request.get_json() or {})
        payroll = EnterpriseService.create_payroll(payload.model_dump())
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Création paie #{payroll.id}")
        return jsonify(payroll_to_dict(payroll)), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@payroll_bp.put("/<int:payroll_id>")
@jwt_required()
@permission_required("Voir salaires")
def update_payroll(payroll_id: int):
    """Met à jour une fiche de paie existante."""
    try:
        payload = PayrollUpdateSchema.model_validate(request.get_json() or {})
        payroll = EnterpriseService.update_payroll(payroll_id, payload.model_dump(exclude_none=True))
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Modification paie #{payroll.id}")
        return jsonify(payroll_to_dict(payroll))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@payroll_bp.delete("/<int:payroll_id>")
@jwt_required()
@permission_required("Voir salaires")
def delete_payroll(payroll_id: int):
    """Supprime une fiche de paie."""
    EnterpriseService.delete_payroll(payroll_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Suppression paie #{payroll_id}")
    return jsonify({"message": "Paie supprimée"})


@payroll_bp.get("/<int:payroll_id>/payslip")
@jwt_required()
@permission_required("Voir salaires")
def export_payslip(payroll_id: int):
    """Génère et retourne le chemin d'une fiche de paie PDF."""
    payroll = Payroll.query.get(payroll_id)
    if not payroll:
        return jsonify({"error": "Paie introuvable"}), 404

    folder = current_app.config["PAYSLIP_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"payslip_{payroll_id}.pdf")

    payload = {
        "Employé": f"{payroll.employee.first_name} {payroll.employee.last_name}",
        "Salaire de base": payroll.base_salary,
        "Prime": payroll.bonus,
        "Heures supplémentaires": payroll.overtime_hours,
        "Déductions": payroll.deductions,
        "Impôts": payroll.taxes,
        "Salaire net": payroll.net_salary,
        "Date paiement": payroll.paid_at.strftime("%Y-%m-%d %H:%M"),
    }
    generate_payslip_pdf(file_path, payload)

    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Export fiche de paie #{payroll_id}")

    return jsonify({"message": "PDF généré", "file_path": file_path})
