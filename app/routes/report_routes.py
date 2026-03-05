"""
Rôle du fichier:
Expose les endpoints de reporting (KPI, statistiques RH, comptabilité).
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app.services.enterprise_service import EnterpriseService
from app.utils.rbac import permission_required


report_bp = Blueprint("reports", __name__)


@report_bp.get("/stats")
@jwt_required()
@permission_required("Exporter rapports")
def get_statistics():
    """Retourne les statistiques RH principales (masse salariale, absentéisme, etc.)."""
    return jsonify(EnterpriseService.payroll_statistics())


@report_bp.get("/accounting")
@jwt_required()
@permission_required("Voir comptabilité")
def get_accounting_statistics():
    """Retourne les agrégats comptables pour les graphiques et indicateurs financiers."""
    return jsonify(EnterpriseService.accounting_statistics())
