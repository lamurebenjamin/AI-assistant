import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ui.windows.assistant_file_links import created_file_paths, file_link_markdown


class AssistantFileLinksTests(unittest.TestCase):
    def test_created_file_paths_walks_nested_payload_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.pdf"
            path.touch()
            detail = json.dumps({"result": {"files": [str(path), str(path)]}})
            self.assertEqual(created_file_paths(detail), [str(path)])

    def test_created_file_paths_resolves_relative_paths_from_app_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.txt"
            path.touch()
            with patch(
                "src.ui.windows.assistant_file_links.APP_DIR", directory
            ):
                self.assertEqual(created_file_paths('{"file": "result.txt"}'), [str(path)])

    def test_file_link_markdown_uses_stem_for_display(self):
        link = file_link_markdown("C:/output/report.xlsx")
        self.assertIn("[report]", link)
        self.assertIn("report.xlsx", link)


if __name__ == "__main__":
    unittest.main()
