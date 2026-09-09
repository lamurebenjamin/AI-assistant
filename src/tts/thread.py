# -*- coding: utf-8 -*-
"""Threads Qt pour le préchauffage et la synthèse vocale Kokoro."""

import logging
import os
import re
import unicodedata
from typing import Optional

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
import sounddevice as sd

from src.config.schema import APP_DIR, DEFAULT_CONFIG, LOGGER
from src.rendering.markdown import markdown_to_spoken_text
from src.tts.engine import KokoroEngine


class KokoroWarmupThread(QThread):
    """Précharge Kokoro en arrière-plan au démarrage de l'assistant.

    Permet de réchauffer le contexte CUDA et d'alléger la latence du premier appel.
    """

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

    def run(self):
        try:
            tts_cfg = self.config.get("text_to_speech", DEFAULT_CONFIG["text_to_speech"])
            model_path = KokoroTtsThread.resolve_path(
                tts_cfg.get("model_path", os.path.join("kokoro", "kokoro-v1.0.onnx"))
            )
            voices_path = KokoroTtsThread.resolve_path(
                tts_cfg.get("voices_path", os.path.join("kokoro", "voices-v1.0.bin"))
            )
            if os.path.isfile(model_path) and os.path.isfile(voices_path):
                KokoroEngine.get(model_path, voices_path)
                LOGGER.info("Kokoro préchargé (CUDA).")
        except Exception:
            LOGGER.exception("Préchargement de Kokoro impossible")


class KokoroTtsThread(QThread):
    """Synthèse vocale française locale avec Kokoro ONNX et sounddevice."""

    _g2p_cache = {}

    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, text: str, config: dict, parent=None):
        super().__init__(parent)
        self.text = markdown_to_spoken_text(text)
        self.config = config

    def stop(self):
        self.requestInterruption()
        try:
            sd.stop()
        except Exception:
            pass

    @staticmethod
    def resolve_path(path: str) -> str:
        expanded = os.path.expandvars(os.path.expanduser(str(path)))
        if not os.path.isabs(expanded):
            expanded = os.path.join(APP_DIR, expanded)
        return os.path.normpath(expanded)

    # Alias pour compatibilité
    _resolve_path = staticmethod(resolve_path)

    def _resolve_output_device(self) -> Optional[int]:
        """Résout une sortie audio par identifiant ou par nom partiel."""
        configured_id = self.config.get("output_device")
        configured_name = str(self.config.get("output_device_name", "")).strip()

        if configured_id not in (None, ""):
            try:
                device_id = int(configured_id)
                info = sd.query_devices(device_id, "output")
                if int(info.get("max_output_channels", 0)) > 0:
                    return device_id
            except (TypeError, ValueError, sd.PortAudioError):
                pass

        if configured_name:
            wanted = configured_name.casefold()
            for device_id, info in enumerate(sd.query_devices()):
                if (
                    int(info.get("max_output_channels", 0)) > 0
                    and wanted in str(info.get("name", "")).casefold()
                ):
                    return device_id
            raise RuntimeError(
                f"Sortie audio introuvable : {configured_name}. "
                "Exécutez 'python -m sounddevice' pour obtenir son nom ou son identifiant."
            )

        try:
            return int(sd.default.device[1])
        except (TypeError, ValueError, IndexError):
            return None

    @staticmethod
    def shorten_long_silences(audio, sample_rate: int, max_pause_ms: int = 220):
        """Raccourcit les silences internes excessifs sans couper la parole."""
        audio = np.asarray(audio, dtype=np.float32)
        if audio.size == 0 or sample_rate <= 0:
            return audio

        mono = np.max(np.abs(audio), axis=1) if audio.ndim > 1 else np.abs(audio)
        window = max(1, int(sample_rate * 0.01))
        envelope = np.convolve(mono, np.ones(window) / window, mode="same")
        silence = envelope < 0.002
        minimum_pause = max(1, int(sample_rate * 0.35))
        kept_pause = max(1, int(sample_rate * max_pause_ms / 1000.0))

        transitions = np.diff(np.r_[False, silence, False].astype(np.int8))
        starts = np.flatnonzero(transitions == 1)
        ends = np.flatnonzero(transitions == -1)
        pieces = []
        cursor = 0
        for start, end in zip(starts, ends):
            if start == 0 or end == len(mono) or end - start < minimum_pause:
                continue
            pieces.append(audio[cursor:start])
            center = (start + end) // 2
            left = max(start, center - kept_pause // 2)
            right = min(end, left + kept_pause)
            left = max(start, right - kept_pause)
            pieces.append(audio[left:right])
            cursor = end

        if cursor == 0:
            return audio
        pieces.append(audio[cursor:])
        return np.concatenate(pieces, axis=0)

    # Alias pour compatibilité
    _shorten_long_silences = staticmethod(shorten_long_silences)

    def run(self):
        try:
            model_path = self.resolve_path(
                self.config.get(
                    "model_path", os.path.join("kokoro", "kokoro-v1.0.onnx")
                )
            )
            voices_path = self.resolve_path(
                self.config.get(
                    "voices_path", os.path.join("kokoro", "voices-v1.0.bin")
                )
            )
            missing = [
                p for p in (model_path, voices_path) if not os.path.isfile(p)
            ]
            if missing:
                raise RuntimeError(
                    "Fichier Kokoro introuvable : " + ", ".join(missing)
                )

            speed = max(0.5, min(2.0, float(self.config.get("speed", 1.2))))
            volume = max(0.0, min(1.0, float(self.config.get("volume", 100)) / 100.0))
            voice = str(self.config.get("voice", "ff_siwis"))
            language = str(self.config.get("language", "fr-fr"))

            spoken_text = unicodedata.normalize("NFC", self.text)
            spoken_text = spoken_text.replace("\u2018", "'").replace("\u2019", "'")
            spoken_text = spoken_text.replace("\u201b", "'").replace("\u2032", "'")
            spoken_text = re.sub(r"[\u00ad\u200b\u200c\u200d\ufeff]", "", spoken_text)
            spoken_text = re.sub(r"[ \t]+", " ", spoken_text).strip()

            if not spoken_text:
                return

            kokoro = KokoroEngine.get(model_path, voices_path)

            phonemizer_logger = logging.getLogger("phonemizer")
            previous_level = phonemizer_logger.level
            phonemizer_logger.setLevel(logging.ERROR)
            try:
                samples, sample_rate = kokoro.create(
                    spoken_text,
                    voice,
                    speed=speed,
                    lang=language,
                    is_phonemes=False,
                )
            finally:
                phonemizer_logger.setLevel(previous_level)

            if self.isInterruptionRequested():
                return

            audio = np.asarray(samples, dtype=np.float32) * volume
            audio = self.shorten_long_silences(
                audio,
                int(sample_rate),
                max_pause_ms=int(self.config.get("max_pause_ms", 220)),
            )

            silence_samples = max(1, int(float(sample_rate) * 0.03))
            if audio.ndim == 1:
                leading_silence = np.zeros(silence_samples, dtype=np.float32)
                audio = np.concatenate((leading_silence, audio))
            else:
                leading_silence = np.zeros(
                    (silence_samples, audio.shape[1]),
                    dtype=np.float32,
                )
                audio = np.concatenate((leading_silence, audio), axis=0)

            output_device = self._resolve_output_device()
            sd.check_output_settings(
                device=output_device,
                samplerate=int(sample_rate),
                channels=1 if audio.ndim == 1 else audio.shape[1],
                dtype="float32",
            )
            sd.play(
                audio,
                int(sample_rate),
                device=output_device,
                blocking=False,
            )
            while sd.get_stream().active:
                if self.isInterruptionRequested():
                    sd.stop()
                    return
                self.msleep(50)
            self.finished_ok.emit()
        except Exception as error:
            try:
                sd.stop()
            except Exception:
                pass
            LOGGER.exception("Erreur détaillée de synthèse vocale Kokoro")
            if not self.isInterruptionRequested():
                self.failed.emit(f"{type(error).__name__}: {error}")
