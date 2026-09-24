import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_dpi_validation(scale_factor: str):
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
    os.environ['QT_SCALE_FACTOR'] = scale_factor

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from src.ui.icons import initialize_icons
    initialize_icons()

    from src.config.manager import load_config
    from src.ui.windows.assistant_window import AssistantWindow
    from src.ui.windows.document_dialog import DocumentDialog
    from src.ui.windows.runtime_info_dialog import RuntimeInfoDialog
    from src.ui.windows.settings_dialog import SettingsDialog

    cfg = load_config()
    os.makedirs('output/dpi_validation', exist_ok=True)
    clean_scale = scale_factor.replace('.', '_')

    surfaces = [
        ('assistant', lambda: AssistantWindow()),
        ('settings', lambda: SettingsDialog(cfg)),
        ('document', lambda: DocumentDialog(None)),
        ('runtime_info', lambda: RuntimeInfoDialog(None)),
    ]

    for name, factory in surfaces:
        w = factory()
        w.show()
        app.processEvents()
        pix = w.grab()
        filename = f'ui-{name}-dark-{clean_scale}.png'
        out_path = os.path.join('output', 'dpi_validation', filename)
        pix.save(out_path)
        print(f'{name} @ {scale_factor}x: size={pix.width()}x{pix.height()} -> {out_path}')
        w.close()
        app.processEvents()

if __name__ == '__main__':
    scale = sys.argv[1] if len(sys.argv) > 1 else '1.25'
    run_dpi_validation(scale)
