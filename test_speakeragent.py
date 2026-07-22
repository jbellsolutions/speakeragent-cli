import argparse
import io
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest import mock

import speakeragent


class ConfigTests(unittest.TestCase):
    def args(self, **overrides):
        values = {
            "api_url": None,
            "api_key": None,
            "speaker_id": None,
            "allow_insecure_localhost": False,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_requires_https(self):
        env = {
            "SPEAKERAGENT_API_URL": "http://api.example.com",
            "SPEAKERAGENT_API_KEY": "secret",
            "SPEAKERAGENT_SPEAKER_ID": "speaker_1",
        }
        with mock.patch.dict("os.environ", env, clear=True), self.assertRaises(SystemExit):
            speakeragent._cfg(self.args())

    def test_allows_explicit_insecure_localhost(self):
        env = {
            "SPEAKERAGENT_API_URL": "http://localhost:8000",
            "SPEAKERAGENT_API_KEY": "secret",
            "SPEAKERAGENT_SPEAKER_ID": "speaker_1",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            result = speakeragent._cfg(self.args(allow_insecure_localhost=True))
        self.assertEqual(result[0], "http://localhost:8000")

    def test_api_key_argument_warns(self):
        stderr = io.StringIO()
        args = self.args(
            api_url="https://api.example.com", api_key="secret", speaker_id="speaker_1"
        )
        with redirect_stderr(stderr):
            speakeragent._cfg(args)
        self.assertIn("shell history", stderr.getvalue())


class ValidationTests(unittest.TestCase):
    def test_strict_bool(self):
        self.assertTrue(speakeragent._strict_bool("true"))
        self.assertFalse(speakeragent._strict_bool("false"))
        with self.assertRaises(argparse.ArgumentTypeError):
            speakeragent._strict_bool("yes")

    def test_rejects_path_in_id(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            speakeragent._validate_id("../another-record")

    def test_redacts_nested_sensitive_fields(self):
        value = {"Contact Email": "host@example.com", "nested": {"Email Draft": "secret"}}
        self.assertEqual(
            speakeragent._redact(value),
            {"Contact Email": "[redacted]", "nested": {"Email Draft": "[redacted]"}},
        )

    def test_safe_url_removes_query(self):
        self.assertEqual(
            speakeragent._safe_url("https://api.example.com/path?speaker_id=secret"),
            "https://api.example.com/path",
        )

    def test_podcast_url_always_has_speaker_id(self):
        result = speakeragent._podcast_url(
            "https://api.example.com", "/api/podcasts/rec1", "speaker_1"
        )
        self.assertEqual(result, "https://api.example.com/api/podcasts/rec1?speaker_id=speaker_1")

    def test_speaker_id_can_follow_command(self):
        args = speakeragent.build_parser().parse_args(
            ["podcasts", "--speaker-id", "speaker_2"]
        )
        self.assertEqual(args.speaker_id, "speaker_2")

    def test_global_speaker_id_still_works(self):
        args = speakeragent.build_parser().parse_args(
            ["--speaker-id", "speaker_3", "podcasts"]
        )
        self.assertEqual(args.speaker_id, "speaker_3")


class RedirectTests(unittest.TestCase):
    def test_blocks_cross_origin_redirect(self):
        handler = speakeragent._SameOriginRedirectHandler()
        request = urllib.request.Request(
            "https://api.example.com/start", headers={"X-API-Key": "secret"}
        )
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://evil.example/collect",
            )


if __name__ == "__main__":
    unittest.main()
