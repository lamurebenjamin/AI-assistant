import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.audio.recorder import AudioRecorderThread
from src.tts.thread import KokoroTtsThread


class ThreadLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_audio_stop_records_tail_request_without_hardware(self):
        thread = AudioRecorderThread(None, 16000, 1, test_only=True, release_tail_ms=300)
        thread.stop_recording()
        self.assertFalse(thread._running)
        self.assertIsNotNone(thread._stop_at)

    def test_audio_run_test_only_uses_mocked_stream_and_closes_it(self):
        stream = MagicMock()
        stream.start.side_effect = lambda: None
        with patch("src.audio.recorder.sd.query_devices", return_value={"default_samplerate": 16000}), \
             patch("src.audio.recorder.sd.check_input_settings"), \
             patch("src.audio.recorder.sd.InputStream", return_value=stream), \
             patch.object(AudioRecorderThread, "isInterruptionRequested", side_effect=[False, True]), \
             patch.object(AudioRecorderThread, "msleep"):
            thread = AudioRecorderThread(None, 16000, 1, test_only=True)
            thread.run()
        stream.start.assert_called_once()
        stream.stop.assert_called_once()
        stream.close.assert_called_once()

    def test_tts_stop_requests_interruption_and_stops_audio(self):
        thread = KokoroTtsThread("hello", {})
        with patch.object(thread, "requestInterruption") as interrupt, patch("src.tts.thread.sd.stop") as stop:
            thread.stop()
        interrupt.assert_called_once()
        stop.assert_called_once()

    def test_tts_run_reports_missing_model_without_kokoro(self):
        thread = KokoroTtsThread("hello", {"model_path": "missing.onnx", "voices_path": "missing.bin"})
        failed = []
        thread.failed.connect(failed.append)
        with patch("src.tts.thread.KokoroTtsThread.resolve_path", side_effect=lambda value: value), \
             patch("src.tts.thread.sd.stop"):
            thread.run()
        self.assertTrue(failed)
        self.assertIn("RuntimeError", failed[0])


if __name__ == "__main__":
    unittest.main()
