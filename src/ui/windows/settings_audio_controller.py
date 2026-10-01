"""Peripheriques d'entree audio et test du microphone."""
import sounddevice as sd
from PySide6.QtCore import Qt

from src.audio.recorder import AudioRecorderThread
from src.config.schema import LOGGER


def refresh_audio_devices(self):
    saved_name = self.temp_voice_config.get("input_device_name", "")
    self.voice_device_combo.clear()
    self.voice_device_combo.addItem("Périphérique par défaut de Windows", None)
    try:
        devices = sd.query_devices()
        for index, device in enumerate(devices):
            if int(device.get("max_input_channels", 0)) > 0:
                name = str(device.get("name", f"Microphone {index}"))
                self.voice_device_combo.addItem(name, {"index": index, "name": name})
        match = self.voice_device_combo.findText(saved_name, Qt.MatchExactly) if saved_name else 0
        if match < 0:
            match = 0
            self.voice_device_info.setText("Le microphone enregistré est indisponible. Le périphérique Windows par défaut sera utilisé.")
        else:
            self.voice_device_info.setText("")
        self.voice_device_combo.setCurrentIndex(match)
        self.voice_test_btn.setEnabled(self.voice_device_combo.count() > 0)
    except Exception as error:  # noqa: BLE001
        LOGGER.warning("Impossible d'énumérer les microphones: %s", error)
        self.voice_device_info.setText("Aucun microphone disponible.")
        self.voice_test_btn.setEnabled(False)


def toggle_microphone_test(self):
    if self.mic_test_thread is not None and self.mic_test_thread.isRunning():
        self.mic_test_thread.stop_recording()
        self.voice_test_btn.setText("Tester le microphone")
        return
    data = self.voice_device_combo.currentData()
    device = data.get("index") if isinstance(data, dict) else None
    self.mic_test_thread = AudioRecorderThread(device, 16000, 3600.0, test_only=True, parent=self)
    self.mic_test_thread.level_changed.connect(self.voice_test_level.setValue)
    self.mic_test_thread.error.connect(self.voice_device_info.setText)
    self.mic_test_thread.finished.connect(lambda: self.voice_test_btn.setText("Tester le microphone"))
    self.voice_test_btn.setText("Arrêter le test")
    self.mic_test_thread.start()
