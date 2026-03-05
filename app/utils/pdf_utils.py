"""
Rôle du fichier:
Génère des documents PDF (fiches de paie, rapports exportables) à partir des données métier.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_payslip_pdf(file_path: str, payload: dict) -> str:
    """Génère une fiche PDF simple à partir d'un dictionnaire clé/valeur."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    pdf = canvas.Canvas(file_path, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Fiche de paie")

    y -= 40
    pdf.setFont("Helvetica", 11)
    for key, value in payload.items():
        pdf.drawString(50, y, f"{key}: {value}")
        y -= 20

    pdf.save()
    return file_path
