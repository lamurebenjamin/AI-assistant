import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.llm.server_manager import LlamaServerManager


class ServerManagerTests(unittest.TestCase):
    def test_start_validates_files_and_deduplicates_running_start(self):
        manager = LlamaServerManager()
        with tempfile.TemporaryDirectory() as directory:
            exe, model = os.path.join(directory, "server.exe"), os.path.join(directory, "model.gguf")
            open(exe, "w").close()
            open(model, "w").close()
            process = MagicMock(pid=42)
            process.poll.return_value = None
            with patch("src.llm.server_manager.APP_DIR", directory), patch(
                "src.llm.server_manager.subprocess.Popen", return_value=process
            ) as popen:
                ok, message = manager.start({"llama_server": {"executable": exe, "model": model, "arguments": ["--port", "8080"]}})
                self.assertTrue(ok)
                self.assertIn("42", message)
                self.assertEqual(popen.call_args.kwargs["cwd"], directory)
                command = popen.call_args.args[0]
                self.assertEqual(command[-2], "--api-key")
                self.assertTrue(manager.auth_token)
                self.assertNotIn(manager.auth_token, message)
                self.assertEqual(manager.start({}), (True, "Serveur déjà démarré"))
            manager.stop()
            self.assertIsNone(manager.auth_token)

    def test_start_missing_files_and_popen_error(self):
        manager = LlamaServerManager()
        self.assertFalse(manager.start({"llama_server": {"executable": "missing", "model": "model"}})[0])
        with tempfile.TemporaryDirectory() as directory:
            exe, model = os.path.join(directory, "server"), os.path.join(directory, "model")
            open(exe, "w").close(); open(model, "w").close()
            with patch("src.llm.server_manager.APP_DIR", directory), patch(
                "src.llm.server_manager.subprocess.Popen", side_effect=OSError("boom")
            ):
                ok, message = manager.start({"llama_server": {"executable": exe, "model": model}})
            self.assertFalse(ok)
            self.assertIn("boom", message)
            self.assertIsNone(manager.process)

    def test_stop_terminates_and_kills_on_timeout(self):
        manager = LlamaServerManager()
        process = MagicMock(pid=7)
        process.poll.return_value = None
        process.wait.side_effect = [__import__("subprocess").TimeoutExpired("x", 8), None]
        manager.process = process
        self.assertEqual(manager.stop(), (True, "Serveur arrêté"))
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertIsNone(manager.process)


if __name__ == "__main__":
    unittest.main()
