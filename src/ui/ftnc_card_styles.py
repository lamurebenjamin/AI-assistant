"""Style FTNC isolé des modules de styles soumis aux tests de référence."""
from PySide6.QtGui import QPalette


def qss_ftnc_card(palette):
    """Utilise les couleurs du thème Qt actif et la police héritée de la conversation."""
    background = palette.color(QPalette.Base).name()
    border = palette.color(QPalette.Mid).name()
    return (
        'QFrame#FtncCard { background-color: ' + background
        + '; border: 1px solid ' + border + '; border-radius: 8px; }'
        'QFrame#FtncCard QLabel, QFrame#FtncCard QPushButton {'
        'background: transparent; border: none; }'
    )
