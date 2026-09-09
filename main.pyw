"""Point d'entrée principal moderne de l'Assistant IA."""

# IMPORTANT — Windows : onnxruntime-gpu doit être initialisé AVANT PyQt5.
# Si Qt est chargé en premier, ses DLLs CUDA bloquent l'initialisation
# d'onnxruntime (DLL load failed / error 1114). Ce bloc garantit l'ordre.
try:
    import onnxruntime as _ort  # noqa: F401
except Exception:
    pass  # Dégradé en douceur si ONNX absent — le TTS sera simplement indisponible.

import sys
from src.app.application import run

if __name__ == "__main__":
    sys.exit(run())
