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

    def test_test_key_selects_test_api_and_owned_speaker(self):
        env = {
            "SPEAKERAGENT_API_KEY": "sa_test_abcdefghijklmnopqrstuvwxyz",
            "SPEAKERAGENT_API_URL": "https://untrusted.example",
            "SPEAKERAGENT_SPEAKER_ID": "wrong_speaker",
        }
        context = {"authenticated": True, "speaker_id": "speaker_1", "scopes": []}
        with mock.patch.dict("os.environ", env, clear=True), mock.patch.object(
            speakeragent, "_req", return_value=context
        ) as request:
            result = speakeragent._cfg(self.args())
        self.assertEqual(result, (speakeragent.TEST_API_URL, env["SPEAKERAGENT_API_KEY"], "speaker_1"))
        request.assert_called_once_with(
            "GET",
            f"{speakeragent.TEST_API_URL}/api/automation-keys/current",
            env["SPEAKERAGENT_API_KEY"],
        )

    def test_live_key_selects_live_api(self):
        key = "sa_live_abcdefghijklmnopqrstuvwxyz"
        with mock.patch.dict("os.environ", {"SPEAKERAGENT_API_KEY": key}, clear=True), mock.patch.object(
            speakeragent, "_req", return_value={"speaker_id": "speaker_1"}
        ):
            result = speakeragent._cfg(self.args())
        self.assertEqual(result[0], speakeragent.LIVE_API_URL)
        self.assertEqual(result[0], speakeragent.TEST_API_URL)

    def test_customer_key_rejects_explicit_routing_overrides(self):
        key = "sa_test_abcdefghijklmnopqrstuvwxyz"
        with mock.patch.dict("os.environ", {"SPEAKERAGENT_API_KEY": key}, clear=True):
            with self.assertRaises(SystemExit):
                speakeragent._cfg(self.args(api_url="https://example.com"))
            with self.assertRaises(SystemExit):
                speakeragent._cfg(self.args(speaker_id="speaker_2"))


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


class ScoutRunConfirmationTests(unittest.TestCase):
    def generate_args(self, **overrides):
        values = {
            "yes": False,
            "persona_id": None,
            "wait": False,
            "poll_interval": 5,
            "timeout": 900,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_interactive_confirmation_requires_exact_yes(self):
        with mock.patch.object(speakeragent.sys.stdin, "isatty", return_value=True), mock.patch(
            "builtins.input", return_value="no"
        ), self.assertRaises(SystemExit) as raised:
            speakeragent._confirm("Consumes one scout run.")
        self.assertIn("Cancelled", str(raised.exception))

    def test_non_interactive_run_requires_yes_flag(self):
        with mock.patch.object(speakeragent.sys.stdin, "isatty", return_value=False), self.assertRaises(
            SystemExit
        ) as raised:
            speakeragent._confirm("Consumes one scout run.")
        self.assertIn("--yes", str(raised.exception))

    def test_yes_flag_skips_prompt(self):
        with mock.patch("builtins.input") as prompt:
            speakeragent._confirm("Consumes one scout run.", yes=True)
        prompt.assert_not_called()

    def test_personal_and_agency_runs_share_confirmation_gate(self):
        cases = [
            ("automation_key", "speaker_1", "speaker 'speaker_1'"),
            ("agency_key", "agency_speaker_1", "agency speaker 'agency_speaker_1'"),
        ]
        for authorization_model, speaker_id, expected_target in cases:
            with self.subTest(authorization_model=authorization_model):
                args = self.generate_args()

                def config(value):
                    value._automation_context = {
                        "authorization_model": authorization_model,
                    }
                    return "https://api.example.com", "key", speaker_id

                with mock.patch.object(speakeragent, "_cfg", side_effect=config), mock.patch.object(
                    speakeragent, "_confirm"
                ) as confirm, mock.patch.object(
                    speakeragent, "_req", return_value={"status": "started"}
                ) as request:
                    speakeragent.cmd_matches_generate(args)
                self.assertIn(expected_target, confirm.call_args.args[0])
                self.assertIn("one monthly scout run", confirm.call_args.args[0])
                request.assert_called_once()

    def test_declined_confirmation_never_starts_scout(self):
        args = self.generate_args()
        with mock.patch.object(
            speakeragent, "_cfg", return_value=("https://api.example.com", "key", "speaker_1")
        ), mock.patch.object(
            speakeragent, "_confirm", side_effect=SystemExit("Cancelled.")
        ), mock.patch.object(speakeragent, "_req") as request, self.assertRaises(SystemExit):
            speakeragent.cmd_matches_generate(args)
        request.assert_not_called()


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
