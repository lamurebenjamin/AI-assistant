import os, sys
sys.path.insert(0, os.path.abspath("."))
from reportlab.pdfgen import canvas
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

os.makedirs("scratch", exist_ok=True)
pdf_path = os.path.abspath("scratch/sample_doc.pdf")
c = canvas.Canvas(pdf_path)
c.drawString(100, 750, "Hello World PDF Test Document")
c.drawString(100, 700, "This is page 1 with some text.")
c.rect(100, 500, 200, 150, fill=1)
c.showPage()
c.save()

app = QApplication([])
from src.ui.icons import initialize_icons
initialize_icons()
from src.ui.windows.document_dialog import DocumentDialog

dlg = DocumentDialog()
dlg.paths = [pdf_path]
dlg._rebuild_image_strip()

pix = QPixmap(dlg.image_strip.size())
dlg.image_strip.render(pix)
pix.save("scratch/rendered_pdf_card.png")
print("Saved rendered_pdf_card.png successfully!")
