# ruff: noqa: N999  — nom PascalCase imposé par le contrat public du skill
"""Façade compatible avec le générateur FTNC fourni par l'utilisateur.

Les fonctions publiques sont préservées; le code est réparti par responsabilité.
Le nom PascalCase est conservé car il fait partie du contrat public du skill.
"""
import re
from pathlib import Path

from .ftnc_document import build_docx
from .ftnc_extraction import extract_nq_data
from .ftnc_word_macro import build_docm

# =========================

def sanitize_filename_part(value, default="NA", max_length=80):
    """Nettoie une valeur pour l'utiliser dans un nom de fichier Windows."""
    value = str(value or default).strip()
    value = re.sub(r'[<>:"/\\|?*]+', '-', value)
    value = re.sub(r'\s+', ' ', value).strip(' .')
    return (value[:max_length].strip() or default)


def build_output_filename(data, extension=".docm"):
    """Construit le nom du fichier FTNC à partir des champs extraits de la NQ."""
    no_nc = sanitize_filename_part(data.get("No. NC"), "MWB2026XXXXXX")
    programme = sanitize_filename_part(data.get("Programme"), "Programme")
    designation = sanitize_filename_part(data.get("Designation"), "Désignation")
    pnr = sanitize_filename_part(data.get("PNR"), "AXXXX")
    quantite = sanitize_filename_part(data.get("Quantité"), "XX")
    return f"[{no_nc}] {programme} - MW - {designation} ({pnr}) - {quantite} pièces{extension}"


def generate_ftnc_from_nq(
    nq_path="NQ.docx",
    output_path=None,
    image_1_path=None,
    image_2_path=None,
    keep_intermediate_docx=False,
    fallback_to_docx=True,
):
    """
    Extrait les données du fichier NQ.docx, complète le document FTNC,
    remplace les informations dans le nom du fichier et dans le contenu,
    puis génère un .docm avec macros si Microsoft Word/pywin32 est disponible.

    Les champs complétés automatiquement à partir de la NQ ne sont pas surlignés.

    Si la génération .docm échoue, un .docx est généré automatiquement lorsque
    fallback_to_docx=True, ce qui permet d'utiliser le script hors environnement Windows/Word.
    """
    data = extract_nq_data(nq_path)

    if output_path is None:
        output_path = build_output_filename(data, extension=".docm")

    try:
        generated_path = build_docm(
            output_path=output_path,
            image_1_path=image_1_path,
            image_2_path=image_2_path,
            keep_intermediate_docx=keep_intermediate_docx,
            data=data,
        )
    except Exception as exc:
        if not fallback_to_docx:
            raise
        docx_output_path = str(Path(output_path).with_suffix(".docx"))
        generated_path = build_docx(
            output_path=docx_output_path,
            image_1_path=image_1_path,
            image_2_path=image_2_path,
            data=data,
        )
        print("Impossible de générer le .docm avec macro dans cet environnement.")
        print(f"Un .docx sans macro a été généré à la place : {generated_path}")
        print(f"Détail de l'erreur .docm : {exc}")

    return generated_path, data

# ═══════════════════════════════════════════════════════════════════
# POINT D'INTÉGRATION WEB — Ajouts pour app.py
# Ne modifie pas le comportement CLI existant.
# ═══════════════════════════════════════════════════════════════════

def run_first_part(docx_path: str, confirmed_reference: str | None = None) -> dict:
    """
    Encapsule la première partie du traitement pour l'interface web.

    Étapes :
    1. Extraction des données via extract_nq_data()
    2. Retour du dictionnaire de données pour vérification de la référence PNR

    Si confirmed_reference est fourni, il remplace la valeur extraite du .docx.
    Cela permet de reprendre le traitement avec une référence validée manuellement.

    Usage depuis app.py :
        data = run_first_part("uploads/nq.docx")
        # → data["PNR"] contient la référence détectée

    Usage avec référence manuelle :
        data = run_first_part("uploads/nq.docx", confirmed_reference="PNR123456")
        # → data["PNR"] == "PNR123456"
    """
    data = extract_nq_data(str(docx_path))

    # Injection optionnelle de la référence confirmée manuellement
    if confirmed_reference:
        data["PNR"] = confirmed_reference.strip()

    return data


def run_second_part(
    docx_path: str,
    data: dict,
    output_path: str | None = None,
    image_1_path: str | None = None,
    image_2_path: str | None = None,
    fallback_to_docx: bool = True,
) -> tuple[str, dict]:
    """
    Encapsule la deuxième partie du traitement pour l'interface web.

    Lance generate_ftnc_from_nq() avec les données enrichies et validées.

    Usage depuis app.py :
        generated_path, data = run_second_part(
            docx_path="uploads/nq.docx",
            data=extracted_data,
            output_path="outputs/ftnc.docm",
        )
    """
    if output_path is None:
        output_path = build_output_filename(data, extension=".docm")

    generated_path, returned_data = generate_ftnc_from_nq(
        nq_path=str(docx_path),
        output_path=str(output_path),
        image_1_path=image_1_path,
        image_2_path=image_2_path,
        fallback_to_docx=fallback_to_docx,
    )
    return generated_path, returned_data

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extrait les données d'une NQ Word et génère automatiquement la FTNC complétée."
    )
    parser.add_argument("nq_path", nargs="?", default="NQ.docx", help="Chemin du fichier NQ.docx")
    parser.add_argument("-o", "--output", default=None, help="Chemin de sortie. Par défaut : nom généré avec les données extraites")
    parser.add_argument("--image-1", default=None, help="Chemin de la première image à insérer")
    parser.add_argument("--image-2", default=None, help="Chemin de la deuxième image à insérer")
    parser.add_argument("--keep-intermediate-docx", action="store_true", help="Conserve le .docx intermédiaire lors de la génération .docm")
    parser.add_argument("--no-fallback-docx", action="store_true", help="N'autorise pas le repli automatique en .docx si le .docm échoue")
    args = parser.parse_args()

    path, extracted_data = generate_ftnc_from_nq(
        nq_path=args.nq_path,
        output_path=args.output,
        image_1_path=args.image_1,
        image_2_path=args.image_2,
        keep_intermediate_docx=args.keep_intermediate_docx,
        fallback_to_docx=not args.no_fallback_docx,
    )

    print("Données extraites :")
    for key, value in extracted_data.items():
        print(f"- {key} : {value}")
    print(f"Document généré : {path}")
