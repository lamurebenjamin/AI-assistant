"""Moteur Kokoro partagé et persistant avec initialisation CUDA optimisée."""

import logging
import threading

LOGGER = logging.getLogger("Assistant.TTS")


class KokoroEngine:
    """Charge Kokoro une seule fois et réutilise la session onnxruntime.

    Recréer l'InferenceSession CUDA à chaque synthèse coûte cher (chargement
    du modèle + initialisation du contexte CUDA + recherche d'algo cuDNN).
    On conserve une seule instance en mémoire, protégée par un verrou,
    et on ne la recrée que si les chemins de modèle changent.
    """

    _lock = threading.Lock()
    _instance = None
    _model_path: str | None = None
    _voices_path: str | None = None

    @classmethod
    def get(cls, model_path: str, voices_path: str):
        with cls._lock:
            if (
                cls._instance is None
                or cls._model_path != model_path
                or cls._voices_path != voices_path
            ):
                try:
                    from kokoro_onnx import Kokoro
                    from onnxruntime import InferenceSession
                except ImportError as exc:
                    raise RuntimeError(
                        f"Kokoro ou ONNX Runtime n'est pas disponible: {exc}"
                    ) from exc

                providers = [
                    (
                        "CUDAExecutionProvider",
                        {
                            "cudnn_conv_algo_search": "DEFAULT",
                            "cudnn_conv_use_max_workspace": "1",
                            "cudnn_conv1d_pad_to_nc1d": "1",
                            "do_copy_in_default_stream": "1",
                        },
                    ),
                    "CPUExecutionProvider",
                ]
                session = InferenceSession(model_path, providers=providers)
                cls._instance = Kokoro.from_session(session, voices_path)
                cls._model_path = model_path
                cls._voices_path = voices_path
            return cls._instance
