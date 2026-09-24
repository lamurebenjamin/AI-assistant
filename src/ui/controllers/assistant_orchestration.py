"""Audio, speech, tray and startup-status orchestration for :class:`AssistantWindow`."""

import copy
import html
import re

import sounddevice as sd
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from src.audio.recorder import AudioRecorderThread
from src.config.manager import save_config
from src.config.schema import DEFAULT_CONFIG, LOGGER
from src.llm.server_manager import get_server_manager
from src.monitoring.server_status import ServerStatusThread
from src.rendering.markdown import markdown_to_spoken_text
from src.tts.thread import KokoroTtsThread
from src.ui.icons import ICONS_DARK


class AssistantOrchestrationController:
    """Own the non-visual audio/TTS and tray-status workflows.

    The window remains the public facade.  Keeping the host as a small
    callback surface also makes this controller usable with a headless Qt
    test double without constructing the complete assistant window.
    """

    def __init__(self, host):
        self.host = host

    def start_server_online_notification(self, tray_icon):
        host = self.host
        host.startup_tray_icon = tray_icon
        host.startup_server_notified = False
        host.startup_status_thread = None
        host.startup_status_timer = QTimer(host)
        host.startup_status_timer.setInterval(1500)
        host.startup_status_timer.timeout.connect(self.check_startup_server_status)
        host.startup_status_timer.start()
        QTimer.singleShot(0, self.check_startup_server_status)

    def check_startup_server_status(self):
        host = self.host
        if host.startup_server_notified:
            return
        if host.startup_status_thread is not None and host.startup_status_thread.isRunning():
            return
        host.startup_status_thread = ServerStatusThread(
            host.config.get("api_url", ""),
            host,
            get_server_manager().auth_token,
        )
        host.startup_status_thread.status_checked.connect(self.handle_startup_server_status)
        host.startup_status_thread.finished.connect(self.on_startup_status_finished)
        host.startup_status_thread.start()

    def on_startup_status_finished(self):
        host = self.host
        thread = host.sender()
        if thread is host.startup_status_thread:
            host.startup_status_thread = None
        if thread is not None:
            thread.deleteLater()

    def handle_startup_server_status(self, online, detail, model_name):
        host = self.host
        if not online or host.startup_server_notified:
            return
        host.startup_server_notified = True
        host.startup_status_timer.stop()
        message = "Le serveur est en ligne et prêt à recevoir des requêtes."
        if model_name and model_name != "Modèle inconnu":
            message += f"\nModèle : {re.sub(r'\\.gguf$', '', model_name, flags=re.IGNORECASE)}"
        host.startup_tray_icon.showMessage("", message, host.startup_tray_icon.icon(), 5000)

    def toggle_speech(self):
        host = self.host
        if host.tts_thread is not None and host.tts_thread.isRunning():
            self.stop_speech()
            return
        _, answer_text = host.split_thinking_and_answer(host.response_text)
        if host.current_request_is_audio:
            _, answer_text = host.parse_audio_response(answer_text)
        answer_text = answer_text.strip()
        if not answer_text:
            host.speak_button.setToolTip("Aucune réponse à lire")
            return
        cfg = host.config.get("text_to_speech", DEFAULT_CONFIG["text_to_speech"])
        host.tts_thread = KokoroTtsThread(answer_text, cfg, host)
        host.tts_thread.finished_ok.connect(host.on_speech_finished)
        host.tts_thread.failed.connect(host.on_speech_failed)
        host.tts_thread.finished.connect(host.tts_thread.deleteLater)
        host.speak_button.setIcon(ICONS_DARK["stop"])
        host.speak_button.setToolTip("Arrêter la lecture")
        host.tts_thread.start()

    def automatic_tts_enabled(self):
        return bool(self.host.config.get("text_to_speech", {}).get("automatic_reading", False))

    def queue_streaming_speech(self, text, flush=False):
        host = self.host
        if not self.automatic_tts_enabled() or host.current_request_is_audio:
            return
        host.tts_streaming_auto = True
        host.tts_stream_buffer += text
        while True:
            match = re.search(r"[.!?…](?:\s+|$)", host.tts_stream_buffer)
            if match is None:
                break
            end = match.end()
            segment = host.tts_stream_buffer[:end].strip()
            if len(markdown_to_spoken_text(segment)) < 24 and not flush:
                next_match = re.search(r"[.!?…](?:\s+|$)", host.tts_stream_buffer[end:])
                if next_match is None:
                    break
                end += next_match.end()
                segment = host.tts_stream_buffer[:end].strip()
            host.tts_stream_buffer = host.tts_stream_buffer[end:].lstrip()
            if markdown_to_spoken_text(segment):
                host.tts_queue.append(segment)
        if flush:
            remaining = host.tts_stream_buffer.strip()
            host.tts_stream_buffer = ""
            if markdown_to_spoken_text(remaining):
                host.tts_queue.append(remaining)
        self._start_next_tts_segment()

    def _start_next_tts_segment(self):
        host = self.host
        if host.tts_thread is not None or not host.tts_queue:
            if host.tts_thread is None and not host.tts_queue and not host.is_generating:
                host.tts_streaming_auto = False
                host.speak_button.setIcon(ICONS_DARK["speak"])
                host.speak_button.setToolTip("Lire la réponse à haute voix")
            return
        segment = host.tts_queue.pop(0)
        cfg = host.config.get("text_to_speech", DEFAULT_CONFIG["text_to_speech"])
        thread = KokoroTtsThread(segment, cfg, host)
        host.tts_thread = thread
        thread.finished_ok.connect(self._on_tts_segment_finished)
        thread.failed.connect(host.on_speech_failed)
        thread.finished.connect(thread.deleteLater)
        host.speak_button.setIcon(ICONS_DARK["stop"])
        host.speak_button.setToolTip("Arrêter la lecture")
        thread.start()

    def _on_tts_segment_finished(self):
        self.host.tts_thread = None
        QTimer.singleShot(0, self._start_next_tts_segment)

    def stop_speech(self):
        host = self.host
        host.tts_queue.clear()
        host.tts_stream_buffer = ""
        host.tts_streaming_auto = False
        if host.tts_thread is not None:
            host.tts_thread.stop()
        self.on_speech_finished()

    def on_speech_finished(self):
        host = self.host
        host.speak_button.setIcon(ICONS_DARK["speak"])
        host.speak_button.setToolTip("Lire la réponse à haute voix")
        host.tts_thread = None

    def on_speech_failed(self, detail):
        host = self.host
        LOGGER.error("Échec de la synthèse vocale Kokoro : %s", detail)
        host.tts_queue.clear()
        host.tts_stream_buffer = ""
        host.tts_streaming_auto = False
        host.speak_button.setIcon(ICONS_DARK["speak"])
        host.speak_button.setToolTip("Synthèse vocale indisponible : " + detail[:120])
        host.tts_thread = None

    def selected_voice_device(self):
        voice = self.host.config.get("voice_input", {})
        saved_name = voice.get("input_device_name", "")
        try:
            devices = sd.query_devices()
            if saved_name:
                for index, device in enumerate(devices):
                    if device.get("name") == saved_name and int(device.get("max_input_channels", 0)) > 0:
                        return index
                LOGGER.warning("Microphone enregistré introuvable, périphérique par défaut utilisé")
            return None
        except sd.PortAudioError:
            LOGGER.warning(
                "Backend audio indisponible, utilisation du périphérique configuré",
                exc_info=True,
            )
            fallback = voice.get("input_device")
            return fallback if isinstance(fallback, int) and fallback >= 0 else None
        except Exception:  # noqa: BLE001
            LOGGER.exception("Erreur inattendue lors de l'interrogation des périphériques audio")
            return None

    def start_voice_recording(self, index):
        host = self.host
        voice = host.config.get("voice_input", {})
        if not 0 <= index < len(host.config["actions"]):
            return
        if not voice.get("enabled", True) or host.voice_sending or (
            host.audio_thread is not None and host.audio_thread.isRunning()
        ):
            return
        host.voice_action_index = index
        host.voice_cancelled = False
        host.recording_indicator.start_recording(host.config["actions"][index]["name"])
        host.audio_thread = AudioRecorderThread(
            self.selected_voice_device(), voice.get("sample_rate", 16000),
            voice.get("maximum_duration", 60.0),
            release_tail_ms=voice.get("release_tail_ms", 700),
            microphone_gain=voice.get("microphone_gain", 2.0), parent=host,
        )
        host.audio_thread.level_changed.connect(host.recording_indicator.set_level)
        host.audio_thread.recorded.connect(host.handle_voice_audio)
        host.audio_thread.error.connect(host.handle_voice_error)
        host.audio_thread.maximum_reached.connect(
            lambda: host.recording_indicator.set_status("Durée maximale atteinte")
        )
        host.audio_thread.start()

    def stop_voice_recording(self, index):
        host = self.host
        if host.voice_action_index != index:
            return
        if host.audio_thread is not None and host.audio_thread.isRunning():
            host.recording_indicator.hide()
            host.audio_thread.stop_recording()

    def cancel_voice_operation(self):
        host = self.host
        host.voice_cancelled = True
        host.voice_action_index = None
        if host.audio_thread is not None and host.audio_thread.isRunning():
            host.audio_thread.stop_recording()
        if host.voice_sending:
            host.stop_generation()
        host.voice_sending = False
        host.recording_indicator.hide()

    def handle_voice_audio(self, audio_data, duration, rms):
        host = self.host
        host.audio_thread = None
        if host.voice_cancelled:
            return
        voice = host.config.get("voice_input", {})
        if not audio_data or duration < voice.get("minimum_duration", 0.3) or rms < voice.get("minimum_rms_level", 0.0001):
            host.recording_indicator.set_status("Aucun son détecté")
            QTimer.singleShot(1200, host.recording_indicator.hide)
            return
        if len(audio_data) > 25 * 1024 * 1024:
            self.handle_voice_error("L’enregistrement audio est trop volumineux.")
            return
        host.recording_indicator.hide()
        host.voice_sending = True
        action_index = host.voice_action_index
        host.voice_action_index = None
        if action_index is not None:
            host.trigger_action(action_index, audio_data=audio_data, audio_format="wav")

    def handle_voice_error(self, message):
        host = self.host
        host.audio_thread = None
        host.voice_sending = False
        host.voice_action_index = None
        host.recording_indicator.hide()
        host.label.setText(f"⚠️ {html.escape(message)}")
        host.show_window()

    def set_automatic_reading_enabled(self, enabled, persist=True):
        host = self.host
        enabled = bool(enabled)
        tts_config = host.config.setdefault("text_to_speech", copy.deepcopy(DEFAULT_CONFIG["text_to_speech"]))
        tts_config["automatic_reading"] = enabled
        if persist:
            save_config(host.config)
        app = QApplication.instance()
        tray_action = getattr(app, "automatic_reading_action", None)
        if tray_action is not None:
            tray_action.setText("Désactiver la lecture à voix haute" if enabled else "Activer la lecture à voix haute")
        if not enabled:
            self.stop_speech()
        LOGGER.info("Lecture automatique des réponses %s.", "activée" if enabled else "désactivée")

    def set_hotkeys_enabled(self, enabled, persist=True):
        """Synchronize global hotkey managers and their tray action."""
        host = self.host
        enabled = bool(enabled)
        app = QApplication.instance()
        for attribute in ("menu_hotkey_manager", "numeric_hotkey_manager"):
            manager = getattr(app, attribute, None)
            if manager is not None:
                manager.set_enabled(enabled)
        voice_manager = getattr(app, "voice_hotkey_manager", None)
        if voice_manager is not None:
            voice_manager.set_enabled(
                enabled and bool(host.config.get("voice_input", {}).get("enabled", True))
            )
        host.config["hotkeys_enabled"] = enabled
        if persist:
            save_config(host.config)
        tray_action = getattr(app, "hotkeys_action", None)
        if tray_action is not None:
            tray_action.setText(
                "Désactiver les raccourcis" if enabled else "Activer les raccourcis"
            )
        state = "activés" if enabled else "désactivés"
        tray_icon = getattr(app, "tray_icon", None)
        if tray_icon is not None:
            tray_icon.setToolTip(f"Assistant IA - Raccourcis {state}")
        LOGGER.info("Raccourcis clavier %s.", state)
