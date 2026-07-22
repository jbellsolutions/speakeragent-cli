import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import speakeragent


CFG = ("https://api.example.com", "secret", "speaker_1")


class FeatureContractTests(unittest.TestCase):
    def capture(self, function, args, responses):
        output = io.StringIO()
        with mock.patch.object(speakeragent, "_cfg", return_value=CFG), mock.patch.object(
            speakeragent, "_req", side_effect=responses
        ) as request, redirect_stdout(output):
            function(args)
        return request, output.getvalue()

    def test_profile_show_uses_speaker_endpoint_and_redacts_email(self):
        args = SimpleNamespace(reveal_sensitive=False)
        request, output = self.capture(
            speakeragent.cmd_profile_show,
            args,
            [{"speaker_id": "speaker_1", "full_name": "Jane", "email": "jane@example.com"}],
        )
        request.assert_called_once_with(
            "GET", "https://api.example.com/api/speaker/speaker_1", "secret"
        )
        self.assertIn('"email": "[redacted]"', output)
        self.assertNotIn("jane@example.com", output)

    def test_profile_edit_uses_put_and_allowed_payload(self):
        args = SimpleNamespace(from_file="profile.json")
        with mock.patch.object(
            speakeragent, "_object_payload", return_value={"bio": "Updated"}
        ):
            request, _ = self.capture(
                speakeragent.cmd_profile_edit, args, [{"id": "rec_speaker"}]
            )
        request.assert_called_once_with(
            "PUT",
            "https://api.example.com/api/speaker/speaker_1",
            "secret",
            {"bio": "Updated"},
        )

    def test_profile_create_uses_registration_without_password(self):
        args = SimpleNamespace(from_file="profile.json")
        payload = {"full_name": "Jane", "email": "jane@example.com"}
        output = io.StringIO()
        with mock.patch.object(
            speakeragent, "_cfg", return_value=(CFG[0], CFG[1], None)
        ) as config, mock.patch.object(
            speakeragent, "_object_payload", return_value=payload
        ), mock.patch.object(
            speakeragent, "_req", return_value={"speaker_id": "jane_123", "status": "pending_payment"}
        ) as request, redirect_stdout(output):
            speakeragent.cmd_profile_create(args)
        config.assert_called_once_with(args, require_speaker=False)
        request.assert_called_once_with(
            "POST",
            "https://api.example.com/api/speakers/register",
            "secret",
            {"full_name": "Jane", "email": "jane@example.com", "send_welcome_email": False},
        )
        self.assertIn("jane_123", output.getvalue())

    def test_profile_file_rejects_unknown_fields_and_passwords(self):
        with tempfile.TemporaryDirectory() as directory:
            unknown = Path(directory) / "unknown.json"
            unknown.write_text(json.dumps({"bio": "ok", "admin": True}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                speakeragent._object_payload(str(unknown), speakeragent.PROFILE_UPDATE_FIELDS)

            password = Path(directory) / "password.json"
            password.write_text(json.dumps({"password": "secret"}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                speakeragent._object_payload(
                    str(password), speakeragent.PROFILE_UPDATE_FIELDS | {"password"}
                )

    def test_matches_generate_requires_confirmation_and_uses_scout_contract(self):
        args = SimpleNamespace(
            yes=False, persona_id="persona_1", wait=False, poll_interval=1, timeout=10
        )
        with mock.patch.object(speakeragent, "_cfg", return_value=CFG), mock.patch.object(
            speakeragent, "_req"
        ) as request, mock.patch.object(speakeragent.sys.stdin, "isatty", return_value=False):
            with self.assertRaises(SystemExit):
                speakeragent.cmd_matches_generate(args)
        request.assert_not_called()

        args.yes = True
        request, _ = self.capture(
            speakeragent.cmd_matches_generate,
            args,
            [{"status": "started", "scouts_remaining": 2}],
        )
        request.assert_called_once_with(
            "POST",
            "https://api.example.com/api/scout/run?speaker_id=speaker_1&persona_id=persona_1",
            "secret",
            {},
        )

    def test_billing_combines_subscription_and_scout_allowance(self):
        args = SimpleNamespace()
        request, output = self.capture(
            speakeragent.cmd_billing_show,
            args,
            [
                {"plan": "Starter", "billing_source": "stripe"},
                {
                    "plan": {
                        "scouts_used": 1,
                        "scouts_remaining": 3,
                        "max_scout_runs": 4,
                        "resets_at": "2026-08-01",
                    }
                },
            ],
        )
        self.assertEqual(request.call_count, 2)
        self.assertIn('"remaining": 3', output)
        self.assertIn('"maximum": 4', output)

    def test_voice_list_redacts_samples_by_default(self):
        args = SimpleNamespace(reveal_sensitive=False)
        _, output = self.capture(
            speakeragent.cmd_voice_samples_list,
            args,
            [[{"id": "sample_1", "sample_text": "private writing"}]],
        )
        self.assertIn("[redacted]", output)
        self.assertNotIn("private writing", output)

    def test_voice_set_requires_attestation_and_replacement_confirmation(self):
        args = SimpleNamespace(
            from_file="samples.json", confirm_own_writing=False, yes=True
        )
        with mock.patch.object(speakeragent, "_cfg", return_value=CFG), mock.patch.object(
            speakeragent, "_req"
        ) as request:
            with self.assertRaises(SystemExit):
                speakeragent.cmd_voice_samples_set(args)
        request.assert_not_called()

        args.confirm_own_writing = True
        args.yes = False
        samples = {
            "samples": [
                {
                    "sample_text": "This is my writing.",
                    "source_type": "email",
                    "is_own_writing_confirmed": True,
                }
            ]
        }
        with mock.patch.object(speakeragent, "_cfg", return_value=CFG), mock.patch.object(
            speakeragent, "_load_json", return_value=samples
        ), mock.patch.object(speakeragent, "_req") as request, mock.patch.object(
            speakeragent.sys.stdin, "isatty", return_value=False
        ):
            with self.assertRaises(SystemExit):
                speakeragent.cmd_voice_samples_set(args)
        request.assert_not_called()

    def test_voice_preview_uses_extended_timeout(self):
        args = SimpleNamespace()
        request, _ = self.capture(
            speakeragent.cmd_voice_preview,
            args,
            [{"hook": "Example", "cta": "Listen"}],
        )
        request.assert_called_once_with(
            "POST",
            "https://api.example.com/api/speaker/speaker_1/preview-voice",
            "secret",
            {},
            timeout=60,
        )

    def test_old_commands_still_parse(self):
        parser = speakeragent.build_parser()
        cases = [
            ["podcasts"],
            ["show", "rec1"],
            ["email", "rec1"],
            ["refresh", "rec1"],
            ["status", "rec1", "Contacted"],
            ["saved", "rec1", "true"],
        ]
        for command in cases:
            with self.subTest(command=command):
                self.assertTrue(callable(parser.parse_args(command).fn))


if __name__ == "__main__":
    unittest.main()
