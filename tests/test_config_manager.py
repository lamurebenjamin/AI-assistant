import json
import tempfile
import unittest
from pathlib import Path

from src.config.manager import load_config, save_config
from src.config.schema import DEFAULT_CONFIG


class ConfigManagerTests(unittest.TestCase):
    def write(self, value):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(value, handle)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return handle.name

    def test_missing_file_returns_independent_defaults(self):
        first = load_config("does-not-exist.json")
        first["actions"].clear()
        self.assertEqual(load_config("does-not-exist.json"), DEFAULT_CONFIG)

    def test_migrates_piper_and_legacy_voice_values(self):
        path = self.write({
            "text_to_speech": {
                "model_path": "models/piper/fr_FR-siwis-medium.onnx",
                "piper_executable": "piper.exe",
            },
            "voice_input": {
                "minimum_duration": 0.3,
                "minimum_rms_level": 0.0001,
                "release_tail_ms": 300,
            },
        })
        config = load_config(path)
        self.assertEqual(config["text_to_speech"]["model_path"], DEFAULT_CONFIG["text_to_speech"]["model_path"])
        self.assertNotIn("piper_executable", config["text_to_speech"])
        self.assertEqual(config["voice_input"]["minimum_duration"], 0.5)
        self.assertEqual(config["voice_input"]["minimum_rms_level"], 0.003)
        self.assertEqual(config["voice_input"]["release_tail_ms"], 700)

    def test_invalid_values_are_clamped_or_replaced(self):
        path = self.write({
            "llm_max_tokens": "invalid",
            "api_url": "ftp://invalid",
            "llama_server": {"arguments": ["--port", "1", "-b", "10", "-b", "20", "--jinja", "--jinja"]},
            "voice_input": {"maximum_duration": 999, "microphone_gain": 99, "sample_rate": 16000},
            "ctrl9": {"width": 1, "font_size": "bad"},
        })
        config = load_config(path)
        self.assertEqual(config["llm_max_tokens"], DEFAULT_CONFIG["llm_max_tokens"])
        self.assertEqual(config["api_url"], DEFAULT_CONFIG["api_url"])
        self.assertEqual(config["voice_input"]["maximum_duration"], 300.0)
        self.assertEqual(config["voice_input"]["microphone_gain"], 8.0)
        self.assertEqual(config["voice_input"]["sample_rate"], 16000)
        self.assertEqual(config["ctrl9"]["width"], 360)
        self.assertEqual(config["ctrl9"]["font_size"], 14)
        self.assertEqual(config["llama_server"]["arguments"], ["--port", "1", "-b", "10", "--jinja"])

    def test_save_config_uses_json_and_replaces_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "config.json")
            save_config({"hello": "world"}, path)
            self.assertEqual(json.loads(Path(path).read_text(encoding="utf-8")), {"hello": "world"})
            self.assertFalse(Path(path + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
