"""
Rôle du fichier:
Expose les endpoints de gestion des contrats employés.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from pydantic import ValidationError

from app.schemas.payloads import ContractCreateSchema, ContractUpdateSchema
from app.services.enterprise_service import EnterpriseService
from app.utils.activity_logger import log_activity
from app.utils.rbac import permission_required
from app.utils.serializers import contract_to_dict


contract_bp = Blueprint("contracts", __name__)


@contract_bp.get("")
@jwt_required()
@permission_required("Voir employés")
def list_contracts():
    """Retourne la liste des contrats enregistrés."""
    contracts = EnterpriseService.list_contracts()
    return jsonify([contract_to_dict(c) for c in contracts])


@contract_bp.post("")
@jwt_required()
@permission_required("Modifier employés")
def create_contract():
    """Crée un nouveau contrat employé."""
    try:
        payload = ContractCreateSchema.model_validate(request.get_json() or {})
        contract = EnterpriseService.create_contract(payload.model_dump())
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Création contrat #{contract.id}")
        return jsonify(contract_to_dict(contract)), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@contract_bp.put("/<int:contract_id>")
@jwt_required()
@permission_required("Modifier employés")
def update_contract(contract_id: int):
    """Met à jour un contrat existant."""
    try:
        payload = ContractUpdateSchema.model_validate(request.get_json() or {})
        contract = EnterpriseService.update_contract(contract_id, payload.model_dump(exclude_none=True))
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Modification contrat #{contract.id}")
        return jsonify(contract_to_dict(contract))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@contract_bp.delete("/<int:contract_id>")
@jwt_required()
@permission_required("Modifier employés")
def delete_contract(contract_id: int):
    """Supprime un contrat existant."""
    EnterpriseService.delete_contract(contract_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Suppression contrat #{contract_id}")
    return jsonify({"message": "Contrat supprimé"})
