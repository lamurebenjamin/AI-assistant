"""Conversion DOCX vers DOCM via Microsoft Word, lorsque disponible."""
from pathlib import Path

from .ftnc_document import build_docx

VBA_CODE = """
Option Explicit

Private Sub Document_Open()
    UpdateAllTrackedControls
End Sub

Private Sub Document_ContentControlOnExit(ByVal ContentControl As ContentControl, Cancel As Boolean)
    If Left$(ContentControl.Tag, 10) = "Conclusion" Then
        FormatConclusionControl ContentControl
    ElseIf ContentControl.Tag = "Classification" Then
        FormatClassificationControl ContentControl
    ElseIf ContentControl.Tag = "Disposition" Then
        FormatDispositionControl ContentControl
    End If
End Sub

Private Sub UpdateAllTrackedControls()
    Dim cc As ContentControl
    For Each cc In ActiveDocument.ContentControls
        If Left$(cc.Tag, 10) = "Conclusion" Then
            FormatConclusionControl cc
        ElseIf cc.Tag = "Classification" Then
            FormatClassificationControl cc
        ElseIf cc.Tag = "Disposition" Then
            FormatDispositionControl cc
        End If
    Next cc
End Sub

Private Function CleanControlText(ByVal cc As ContentControl) As String
    Dim txt As String
    txt = cc.Range.Text
    txt = Replace(txt, Chr(13), "")
    txt = Replace(txt, Chr(7), "")
    CleanControlText = txt
End Function

Private Sub ApplyBaseControlFont(ByVal cc As ContentControl, ByVal isBold As Boolean, ByVal isItalic As Boolean)
    With cc.Range.Font
        .Name = "Aptos"
        .Size = 11
        .Bold = isBold
        .Italic = isItalic
    End With
End Sub

Private Sub FormatConclusionControl(ByVal cc As ContentControl)
    Dim txt As String
    txt = CleanControlText(cc)
    If cc.Tag = "Conclusion Form" Or cc.Tag = "Conclusion Function" Or cc.Tag = "Conclusion Fit" Then
        ApplyBaseControlFont cc, False, True
        cc.Range.Font.Color = RGB(191, 191, 191)
        Exit Sub
    End If
    ApplyBaseControlFont cc, True, False
    If InStr(1, txt, "Pas d", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(25, 107, 36)
    ElseIf InStr(1, txt, "Impact mineur", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(214, 209, 0)
    ElseIf InStr(1, txt, "Impact majeur", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(233, 113, 50)
    ElseIf InStr(1, txt, "Non acceptable", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(192, 0, 0)
    Else
        cc.Range.Font.Color = RGB(0, 0, 0)
        cc.Range.Font.Bold = False
    End If
End Sub

Private Sub FormatClassificationControl(ByVal cc As ContentControl)
    Dim txt As String
    txt = CleanControlText(cc)
    ApplyBaseControlFont cc, True, False
    If InStr(1, txt, "MINEUR", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(25, 107, 36)
    ElseIf InStr(1, txt, "MAJEUR", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(192, 0, 0)
    Else
        cc.Range.Font.Color = RGB(0, 0, 0)
        cc.Range.Font.Bold = False
    End If
End Sub

Private Sub FormatDispositionControl(ByVal cc As ContentControl)
    Dim txt As String
    txt = CleanControlText(cc)
    ApplyBaseControlFont cc, True, False
    If InStr(1, txt, "Acceptable", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(25, 107, 36)
    ElseIf InStr(1, txt, "Retouche", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(233, 113, 50)
    ElseIf InStr(1, txt, "Rebut", vbTextCompare) > 0 Then
        cc.Range.Font.Color = RGB(192, 0, 0)
    Else
        cc.Range.Font.Color = RGB(0, 0, 0)
        cc.Range.Font.Bold = False
    End If
End Sub
"""


def add_vba_macro_with_word(input_docx_path, output_docm_path, vba_code=VBA_CODE, visible=False):
    """
    Convertit le document généré en .docm et injecte la macro VBA via Microsoft Word.

    Prérequis :
    - Windows ;
    - Microsoft Word installé ;
    - pywin32 installé : pip install pywin32 ;
    - option Word activée : Fichier > Options > Centre de gestion de la confidentialité
      > Paramètres des macros > cocher "Accès approuvé au modèle d'objet du projet VBA".
    """
    import gc
    import os
    import sys
    import time

    if sys.platform != "win32":
        raise RuntimeError("La création automatique d'un .docm avec macro nécessite Microsoft Word sous Windows.")

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("Les modules pywin32 sont requis. Installe-les avec : pip install pywin32") from exc

    input_docx_path = os.path.abspath(str(input_docx_path))
    output_docm_path = os.path.abspath(str(output_docm_path))

    pythoncom.CoInitialize()
    word = None
    doc = None

    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = visible
        word.DisplayAlerts = 0

        doc = word.Documents.Open(input_docx_path, ReadOnly=False, AddToRecentFiles=False)

        vb_project = doc.VBProject
        this_document = vb_project.VBComponents("ThisDocument")
        code_module = this_document.CodeModule

        if code_module.CountOfLines > 0:
            code_module.DeleteLines(1, code_module.CountOfLines)
        code_module.AddFromString(vba_code)

        # 13 = wdFormatXMLDocumentMacroEnabled (.docm)
        doc.SaveAs2(output_docm_path, FileFormat=13)

    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:  # noqa: BLE001, S110 — nettoyage COM : toute exception ignorée intentionnellement
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:  # noqa: BLE001, S110 — nettoyage COM : toute exception ignorée intentionnellement
                pass

        doc = None
        word = None
        gc.collect()
        time.sleep(1)
        pythoncom.CoUninitialize()

    return output_docm_path


def build_docm(
    output_path="[MWB2026000XXX] Programme - MW - Désignation (AXXXXX) - XX pièces.docm",
    image_1_path=None,
    image_2_path=None,
    keep_intermediate_docx=False,
    data=None,
):
    """
    Génère le document Word macro-enabled .docm.
    Nettoyage temporaire robuste pour éviter WinError 32 si Word garde le .docx verrouillé quelques instants.
    """
    import shutil
    import tempfile
    import time

    output_path = Path(output_path).resolve()
    temp_dir = Path(tempfile.mkdtemp(prefix="ftnc_docm_"))
    tmp_docx = temp_dir / "document_sans_macro.docx"

    try:
        build_docx(str(tmp_docx), image_1_path=image_1_path, image_2_path=image_2_path, data=data)
        add_vba_macro_with_word(tmp_docx, output_path)

        if keep_intermediate_docx:
            intermediate = output_path.with_suffix(".intermediaire.docx")
            intermediate.write_bytes(tmp_docx.read_bytes())

        return str(output_path)

    finally:
        for _ in range(10):
            try:
                shutil.rmtree(temp_dir)
                break
            except PermissionError:
                time.sleep(0.5)
            except FileNotFoundError:
                break

# =========================
# GÉNÉRATION À PARTIR D'UNE NQ
