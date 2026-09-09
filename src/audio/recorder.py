# -*- coding: utf-8 -*-
"""Thread d'enregistrement et de prétraitement audio du microphone."""

import io
import time
import wave
from math import gcd
from typing import Optional

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from scipy.signal import resample_poly
import sounddevice as sd

from src.config.schema import LOGGER


class AudioRecorderThread(QThread):
    level_changed = pyqtSignal(int)
    recorded = pyqtSignal(bytes, float, float)
    error = pyqtSignal(str)
    maximum_reached = pyqtSignal()

    def __init__(
        self,
        device,
        target_rate: int,
        maximum_duration: float,
        test_only: bool = False,
        release_tail_ms: int = 300,
        microphone_gain: float = 1.0,
        parent=None,
    ):
        super().__init__(parent)
        self.device = device
        self.target_rate = int(target_rate)
        self.maximum_duration = float(maximum_duration)
        self.test_only = test_only
        self.release_tail_ms = max(0, int(release_tail_ms))
        self.microphone_gain = min(8.0, max(1.0, float(microphone_gain)))
        self._running = True
        self._stop_at: Optional[float] = None

    def stop_recording(self):
        """Conserve une courte fin d'enregistrement après le relâchement."""
        self._running = False
        if self._stop_at is None:
            self._stop_at = time.monotonic() + self.release_tail_ms / 1000.0

    def run(self):
        chunks = []
        block_rms_levels = []
        stream = None
        try:
            info = sd.query_devices(self.device, "input")
            native_rate = self.target_rate
            try:
                sd.check_input_settings(
                    device=self.device,
                    channels=1,
                    dtype="int16",
                    samplerate=native_rate,
                )
            except Exception:
                native_rate = int(round(float(info["default_samplerate"])))
                sd.check_input_settings(
                    device=self.device,
                    channels=1,
                    dtype="int16",
                    samplerate=native_rate,
                )
            started = time.monotonic()
            minimum_capture_until = started + 0.35

            def callback(indata, frames, timing, status):
                if status:
                    LOGGER.warning("État du flux microphone: %s", status)
                block = indata[:, 0].copy()
                if self.microphone_gain > 1.0 and block.size:
                    amplified = block.astype(np.float32) * self.microphone_gain
                    block = np.clip(np.rint(amplified), -32768, 32767).astype(np.int16)
                rms = (
                    float(np.sqrt(np.mean((block.astype(np.float32) / 32768.0) ** 2)))
                    if block.size
                    else 0.0
                )
                self.level_changed.emit(min(100, int(rms * 2000)))
                if not self.test_only:
                    chunks.append(block)
                    block_rms_levels.append(rms)

            stream = sd.InputStream(
                device=self.device,
                channels=1,
                dtype="int16",
                samplerate=native_rate,
                callback=callback,
                blocksize=0,
            )
            stream.start()

            while not self.isInterruptionRequested():
                now = time.monotonic()
                if not self._running:
                    tail_finished = (
                        self.test_only or self._stop_at is None or now >= self._stop_at
                    )
                    if tail_finished and (self.test_only or now >= minimum_capture_until):
                        break
                if not self.test_only and now - started >= self.maximum_duration:
                    self.maximum_reached.emit()
                    break
                self.msleep(20)

            stream.stop()
            if self.test_only:
                return

            samples = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int16)
            if native_rate != self.target_rate and samples.size:
                divisor = gcd(native_rate, self.target_rate)
                converted = resample_poly(
                    samples.astype(np.float32),
                    self.target_rate // divisor,
                    native_rate // divisor,
                )
                samples = np.clip(np.rint(converted), -32768, 32767).astype(np.int16)

            # Prétraitement léger : suppression de l'offset continu et normalisation douce
            if samples.size:
                signal = samples.astype(np.float32) / 32768.0
                signal -= float(np.mean(signal))
                original_rms = float(np.sqrt(np.mean(signal**2)))
                if original_rms > 1e-5:
                    target_rms = 0.12
                    gain = min(6.0, max(1.0, target_rms / original_rms))
                    signal = np.clip(signal * gain, -0.95, 0.95)
                samples = np.rint(signal * 32767.0).astype(np.int16)

            duration = samples.size / float(self.target_rate)
            overall_rms = (
                float(np.sqrt(np.mean((samples.astype(np.float32) / 32768.0) ** 2)))
                if samples.size
                else 0.0
            )
            active_rms = (
                float(np.percentile(block_rms_levels, 90)) if block_rms_levels else 0.0
            )
            rms = max(overall_rms, active_rms)

            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(self.target_rate)
                wav.writeframes(samples.tobytes())

            self.recorded.emit(buffer.getvalue(), duration, rms)
        except Exception as error:
            LOGGER.exception("Erreur de capture audio")
            self.error.emit(f"Microphone indisponible : {error}")
        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
