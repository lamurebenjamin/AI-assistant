import subprocess
import sys
import unittest
from pathlib import Path

from src.llm.contracts import DocumentTurn, LlmMessage


class ContractsAndQualityTests(unittest.TestCase):
    def test_llm_and_document_turn_contracts_accept_runtime_payloads(self):
        message: LlmMessage = {"role": "user", "content": "Question"}
        turn: DocumentTurn = {"role": "assistant", "content": "Réponse"}
        self.assertEqual(message["role"], "user")
        self.assertEqual(turn["content"], "Réponse")

    def test_module_size_check_passes_with_documented_allowlist(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "check_module_sizes.py")],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
