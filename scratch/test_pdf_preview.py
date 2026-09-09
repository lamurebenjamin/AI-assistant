import os, sys
sys.path.insert(0, os.path.abspath("."))
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

def create_pdf_fallback_pixmap(width: int, height: int) -> QPixmap:
    """Génère une illustration élégante et moderne d'un document PDF."""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing, True)
    
    # Feuille blanche avec bordure douce
    sheet = QRectF(1.0, 1.0, width - 2.0, height - 2.0)
    p.setPen(QPen(QColor(0, 0, 0, 35), 1.0))
    p.setBrush(QColor(255, 255, 255))
    p.drawRoundedRect(sheet, 5.0, 5.0)
    
    # Badge rouge "PDF" moderne au centre
    badge_w, badge_h = 38.0, 18.0
    badge_x = (width - badge_w) / 2.0
    badge_y = (height - badge_h) / 2.0 - 6.0
    badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
    
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#E53E3E"))
    p.drawRoundedRect(badge_rect, 3.5, 3.5)
    
    # Texte PDF blanc gras
    p.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", 8, QFont.Bold)
    p.setFont(font)
    p.drawText(badge_rect, Qt.AlignCenter, "PDF")
    
    # Lignes de texte stylisées sous le badge
    line_pen = QPen(QColor(180, 190, 205), 1.8, Qt.SolidLine, Qt.RoundCap)
    p.setPen(line_pen)
    y_lines = badge_y + badge_h + 8.0
    p.drawLine(QPointF(badge_x - 6, y_lines), QPointF(badge_x + badge_w + 6, y_lines))
    p.drawLine(QPointF(badge_x - 2, y_lines + 5.0), QPointF(badge_x + badge_w + 2, y_lines + 5.0))
    
    p.end()
    return pixmap

def style_rendered_pdf_page(source: QPixmap, max_w: int, max_h: int) -> QPixmap:
    """Met en forme la vignette de page PDF avec une découpe et un contour net."""
    shown = source.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    result = QPixmap(shown.size())
    result.fill(Qt.transparent)
    p = QPainter(result)
    p.setRenderHint(QPainter.Antialiasing, True)
    rect = QRectF(0.5, 0.5, shown.width() - 1.0, shown.height() - 1.0)
    clip = QPainterPath()
    clip.addRoundedRect(rect, 5.0, 5.0)
    p.setClipPath(clip)
    p.drawPixmap(0, 0, shown)
    # Contour fin pour délimiter les pages à fond blanc
    p.setPen(QPen(QColor(0, 0, 0, 32), 1.0))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect, 5.0, 5.0)
    p.end()
    return result

app = QApplication([])
fb = create_pdf_fallback_pixmap(86, 60)
os.makedirs("scratch", exist_ok=True)
fb.save("scratch/test_pdf_fallback.png")
print("Saved test_pdf_fallback.png successfully!")
