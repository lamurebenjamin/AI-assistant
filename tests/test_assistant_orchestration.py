import os
import unittest
from unittest.mock import MagicMock, patch

import sounddevice as sd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.ui.controllers.assistant_orchestration import AssistantOrchestrationController


class AssistantOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_host(self):
        host = MagicMock()
        host.config = {
            "text_to_speech": {"automatic_reading": True},
            "voice_input": {},
        }
        host.tts_queue = []
        host.tts_stream_buffer = ""
        host.tts_streaming_auto = False
        host.tts_thread = None
        host.current_request_is_audio = False
        host.is_generating = True
        host.speak_button = MagicMock()
        return host

    def test_streaming_speech_buffers_short_fragments_until_sentence_boundary(self):
        host = self.make_host()
        controller = AssistantOrchestrationController(host)

        with patch.object(controller, "_start_next_tts_segment") as start:
            controller.queue_streaming_speech("Short. ")

        self.assertEqual(host.tts_queue, [])
        self.assertEqual(host.tts_stream_buffer, "Short. ")
        start.assert_called_once()

    def test_failed_speech_clears_queue_and_reports_detail(self):
        host = self.make_host()
        host.tts_queue = ["pending"]
        host.tts_stream_buffer = "remaining"
        controller = AssistantOrchestrationController(host)

        with patch(
            "src.ui.controllers.assistant_orchestration.ICONS_DARK",
            {"speak": MagicMock()},
        ):
            controller.on_speech_failed("model unavailable")

        self.assertEqual(host.tts_queue, [])
        self.assertEqual(host.tts_stream_buffer, "")
        self.assertIsNone(host.tts_thread)
        host.speak_button.setToolTip.assert_called_once_with(
            "Synthèse vocale indisponible : model unavailable"
        )

    def test_startup_status_notifies_tray_once_with_model_name(self):
        host = self.make_host()
        host.startup_server_notified = False
        host.startup_status_timer = MagicMock()
        host.startup_tray_icon = MagicMock()
        controller = AssistantOrchestrationController(host)

        controller.handle_startup_server_status(True, "", "assistant.gguf")
        controller.handle_startup_server_status(True, "", "assistant.gguf")

        host.startup_tray_icon.showMessage.assert_called_once()
        message = host.startup_tray_icon.showMessage.call_args.args[1]
        self.assertIn("Modèle : assistant", message)
        host.startup_status_timer.stop.assert_called_once()

    def test_selected_voice_device_uses_valid_configured_fallback_on_portaudio_error(self):
        host = self.make_host()
        host.config["voice_input"]["input_device"] = 2
        controller = AssistantOrchestrationController(host)

        with patch(
            "src.ui.controllers.assistant_orchestration.sd.query_devices",
            side_effect=sd.PortAudioError("unavailable"),
        ):
            self.assertEqual(controller.selected_voice_device(), 2)

    def test_selected_voice_device_rejects_unexpected_errors(self):
        host = self.make_host()
        host.config["voice_input"]["input_device"] = 2
        controller = AssistantOrchestrationController(host)

        with patch(
            "src.ui.controllers.assistant_orchestration.sd.query_devices",
            side_effect=RuntimeError("unexpected"),
        ):
            self.assertIsNone(controller.selected_voice_device())


if __name__ == "__main__":
    unittest.main()
