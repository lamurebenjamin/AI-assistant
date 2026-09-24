import unittest

from src.documents.thread import DocumentAnalysisThread
from src.llm.client import LlamaThread
from src.monitoring.runtime_info import RuntimeInfoThread
from src.monitoring.server_status import ServerStatusThread


class LocalAuthenticationTests(unittest.TestCase):
    def test_llama_client_adds_bearer_header_without_persisting_token(self):
        thread = LlamaThread("http://127.0.0.1:8080/v1/chat/completions", "", "", "", "model", auth_token="token")
        self.assertEqual(thread._request_headers()["Authorization"], "Bearer token")

    def test_document_client_adds_bearer_header(self):
        thread = DocumentAnalysisThread("http://127.0.0.1:8080", "model", [], "question", auth_token="token")
        self.assertEqual(thread._request_headers()["Authorization"], "Bearer token")

    def test_monitoring_threads_add_bearer_header(self):
        status = ServerStatusThread("http://127.0.0.1:8080", auth_token="token")
        runtime = RuntimeInfoThread("http://127.0.0.1:8080", set(), auth_token="token")
        self.assertEqual(status._request_headers()["Authorization"], "Bearer token")
        self.assertEqual(runtime._request_headers()["Authorization"], "Bearer token")


if __name__ == "__main__":
    unittest.main()
