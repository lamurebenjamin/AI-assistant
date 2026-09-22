import unittest

from src.llm.response_parser import (
    clean_chunk,
    clean_thinking_text,
    parse_audio_response,
    split_thinking_and_answer,
)


class ResponseParserTests(unittest.TestCase):
    def test_clean_chunk_removes_sse_control_tokens(self):
        self.assertEqual(clean_chunk("hello<|channel|>final<|end|>"), "hello")
        self.assertEqual(clean_chunk(""), "")

    def test_thinking_is_separated_and_unclosed_thinking_is_supported(self):
        thinking, answer = split_thinking_and_answer(
            "<think>thinking process: plan\nstep</think><think>more</think>Final"
        )
        self.assertEqual(thinking, "plan\nstepmore")
        self.assertEqual(answer, "Final")
        self.assertEqual(split_thinking_and_answer("before <think>unfinished")[1], "before")
        self.assertEqual(clean_thinking_text("Thinking Process: x"), "x")

    def test_audio_response_extracts_transcript_and_answer(self):
        transcript, answer = parse_audio_response(
            "<transcript>  hello   world </transcript><answer> final </answer>"
        )
        self.assertEqual(transcript, "hello world")
        self.assertEqual(answer, "final")
        self.assertEqual(parse_audio_response("<transcript>partial</transcript> tail"), ("partial", "tail"))
        self.assertEqual(parse_audio_response("plain response"), ("", "plain response"))
        self.assertEqual(parse_audio_response("<transcript>pending"), ("", ""))


if __name__ == "__main__":
    unittest.main()
