import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

import speakeragent


TEST_KEY = "sa_test_abcdefghijklmnopqrstuvwxyz"
LIVE_KEY = "sa_live_abcdefghijklmnopqrstuvwxyz"
LEGACY_KEY = "existing-deployment-key"
CFG = ("https://api.example.com", TEST_KEY, "speaker_1")


class ApiKeyValidationTests(unittest.TestCase):
    def test_test_live_and_legacy_key_types(self):
        self.assertEqual(speakeragent._validate_api_key(TEST_KEY), "test")
        self.assertEqual(speakeragent._validate_api_key(LIVE_KEY), "live")
        self.assertEqual(speakeragent._validate_api_key(LEGACY_KEY), "legacy")

    def test_prefixed_keys_require_complete_supported_format(self):
        malformed = [
            "sa_test_short",
            "sa_live_short",
            "sa_test_abcdefghijklmnopqrstuv!@",
            "sa_live_abcdefghijklmnopqrstuv wx",
        ]
        for key in malformed:
            with self.subTest(key=key), self.assertRaises(SystemExit) as raised:
                speakeragent._validate_api_key(key)
            self.assertNotIn(key, str(raised.exception))

    def test_legacy_key_with_whitespace_is_rejected_without_echo(self):
        key = "legacy secret value"
        with self.assertRaises(SystemExit) as raised:
            speakeragent._validate_api_key(key)
        self.assertNotIn(key, str(raised.exception))


class AuthCheckTests(unittest.TestCase):
    def test_auth_check_is_read_only_and_never_prints_full_test_key(self):
        output = io.StringIO()
        args = SimpleNamespace()
        with mock.patch.object(speakeragent, "_cfg", return_value=CFG), mock.patch.object(
            speakeragent,
            "_req",
            return_value={
                "authenticated": True,
                "authorization_model": "automation_key",
                "speaker_scope_verified": True,
                "scopes": ["podcasts:read"],
            },
        ) as request, redirect_stdout(output):
            speakeragent.cmd_auth_check(args)

        request.assert_called_once_with(
            "GET",
            "https://api.example.com/api/automation-keys/current?speaker_id=speaker_1",
            TEST_KEY,
        )
        result = json.loads(output.getvalue())
        self.assertTrue(result["authenticated"])
        self.assertTrue(result["speaker_scope_verified"])
        self.assertEqual(result["authorization_model"], "automation_key")
        self.assertEqual(result["scopes"], ["podcasts:read"])
        self.assertEqual(result["key_preview"], "sa_test_...")
        self.assertNotIn(TEST_KEY, output.getvalue())

    def test_auth_check_hides_legacy_key(self):
        output = io.StringIO()
        with mock.patch.object(
            speakeragent, "_cfg", return_value=(CFG[0], LEGACY_KEY, CFG[2])
        ), mock.patch.object(speakeragent, "_req", return_value={}), redirect_stdout(output):
            speakeragent.cmd_auth_check(SimpleNamespace())
        self.assertIn('"key_preview": "legacy (hidden)"', output.getvalue())
        self.assertNotIn(LEGACY_KEY, output.getvalue())

    def test_server_error_cannot_echo_full_key(self):
        error_body = io.BytesIO(
            json.dumps({"detail": f"invalid API key {TEST_KEY}"}).encode("utf-8")
        )
        error = urllib.error.HTTPError(
            "https://api.example.com/api/speaker/speaker_1",
            401,
            "Unauthorized",
            {},
            error_body,
        )
        with mock.patch.object(speakeragent._OPENER, "open", side_effect=error):
            with self.assertRaises(SystemExit) as raised:
                speakeragent._req(
                    "GET", "https://api.example.com/api/speaker/speaker_1", TEST_KEY
                )
        message = str(raised.exception)
        self.assertNotIn(TEST_KEY, message)
        self.assertIn("[redacted]", message)
        self.assertIn("401", message)

    def test_auth_check_parser_accepts_speaker_override(self):
        args = speakeragent.build_parser().parse_args(
            ["auth", "check", "--speaker-id", "speaker_2"]
        )
        self.assertEqual(args.speaker_id, "speaker_2")
        self.assertIs(args.fn, speakeragent.cmd_auth_check)


class CommandSurfaceRegressionTests(unittest.TestCase):
    def test_all_existing_command_paths_still_parse(self):
        parser = speakeragent.build_parser()
        commands = [
            ["podcasts"],
            ["show", "rec1"],
            ["email", "rec1"],
            ["refresh", "rec1"],
            ["status", "rec1", "Contacted"],
            ["saved", "rec1", "true"],
            ["profile", "show"],
            ["profile", "create", "--from", "profile.json"],
            ["profile", "edit", "--from", "profile.json"],
            ["matches", "generate", "--yes"],
            ["matches", "status"],
            ["billing", "show"],
            ["voice", "samples", "list"],
            [
                "voice",
                "samples",
                "set",
                "--from",
                "samples.json",
                "--confirm-own-writing",
                "--yes",
            ],
            ["voice", "status"],
            ["voice", "preview"],
            ["auth", "check"],
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(callable(parser.parse_args(command).fn))


if __name__ == "__main__":
    unittest.main()
