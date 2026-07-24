#!/usr/bin/env python3
"""Secure, stdlib-only CLI for SpeakerAgent.ai podcast leads."""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


STATUSES = ("New", "Contacted", "Replied", "Booked", "Passed")
TRIAGE_VALUES = ("GREEN", "YELLOW", "RED")
SENSITIVE_FIELDS = {
    "Contact Email",
    "Contact LinkedIn",
    "Contact Twitter",
    "Contact Bio",
    "Email Subject",
    "Email Draft",
    "Booking URL",
    "Guest Form URL",
}
SENSITIVE_FIELDS_NORMALIZED = {
    "contact email",
    "contact linkedin",
    "contact twitter",
    "contact bio",
    "email subject",
    "email draft",
    "booking url",
    "guest form url",
    "email",
    "notes",
    "speaker sheet",
    "speaker_sheet",
    "attachments",
    "password",
    "password_hash",
    "client_secret",
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
AUTOMATION_KEY_PATTERN = re.compile(r"^sa_(test|live)_[A-Za-z0-9_-]{24,}$")
TEST_API_URL = "https://speakeragent-integration-test-production.up.railway.app"
# Temporary alpha behavior: live-prefixed customer keys still use the test API.
LIVE_API_URL = TEST_API_URL
PROFILE_UPDATE_FIELDS = {
    "full_name",
    "email",
    "tagline",
    "bio",
    "topics",
    "target_industries",
    "min_honorarium",
    "years_experience",
    "location",
    "website",
    "credentials",
    "linkedin",
    "speaker_sheet",
    "notes",
    "conference_year",
    "conference_tier",
    "zip_code",
}
PROFILE_CREATE_FIELDS = PROFILE_UPDATE_FIELDS | {"send_welcome_email", "partner_id", "voice_samples"}
PROFILE_DISPLAY_FIELDS = PROFILE_UPDATE_FIELDS | {"speaker_id", "persona_id", "plan", "status"}
VOICE_SOURCE_TYPES = {"email", "linkedin", "message", "other"}


def _fail(message):
    raise SystemExit(message)


def _validate_id(value, label="id"):
    if not ID_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            f"{label} must contain only letters, numbers, underscores, or hyphens (max 128)."
        )
    return value


def _strict_bool(value):
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise argparse.ArgumentTypeError("value must be exactly true or false")


def _positive_int(value):
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be an integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return number


def _api_key_type(key):
    if key.startswith("sa_test_"):
        return "test"
    if key.startswith("sa_live_"):
        return "live"
    return "legacy"


def _validate_api_key(key):
    if not isinstance(key, str) or not key or any(character.isspace() for character in key):
        _fail("SPEAKERAGENT_API_KEY is invalid.")
    key_type = _api_key_type(key)
    if key_type != "legacy" and not AUTOMATION_KEY_PATTERN.fullmatch(key):
        _fail(
            f"The sa_{key_type}_ API key is malformed. Copy the complete key again; "
            "automation keys contain at least 24 characters after the prefix."
        )
    return key_type


def _cfg(a, require_speaker=True):
    supplied_url = getattr(a, "api_url", None)
    supplied_key = getattr(a, "api_key", None)
    supplied_speaker = getattr(a, "speaker_id", None)
    key = supplied_key or os.getenv("SPEAKERAGENT_API_KEY")
    if not key:
        _fail("Set SPEAKERAGENT_API_KEY.")
    key_type = _validate_api_key(key)
    if supplied_key:
        print(
            "warning: --api-key can leak through shell history and process listings; "
            "use SPEAKERAGENT_API_KEY instead.",
            file=sys.stderr,
        )

    if key_type in {"test", "live"}:
        if supplied_url:
            _fail(
                "Customer API keys select their SpeakerAgent API automatically; remove --api-url."
            )
        url = TEST_API_URL if key_type == "test" else LIVE_API_URL
        context = _req("GET", f"{url}/api/automation-keys/current", key)
        if context.get("authorization_model") == "agency_key":
            sid = supplied_speaker or os.getenv("SPEAKERAGENT_SPEAKER_ID")
            if sid:
                try:
                    sid = _validate_id(sid, "speaker-id")
                except argparse.ArgumentTypeError as error:
                    _fail(str(error))
            if require_speaker and not sid:
                _fail(
                    "This agency API key requires a speaker. Use --speaker-id or set "
                    "SPEAKERAGENT_SPEAKER_ID. Run `speakeragent speakers list` to see available seats."
                )
            setattr(a, "_automation_context", context)
            return url, key, sid
        if supplied_speaker:
            _fail(
                "Personal customer API keys select their owned speaker automatically; "
                "remove --speaker-id."
            )
        sid = context.get("speaker_id")
        if not sid:
            _fail("The API key is valid but has no speaker assigned.")
        try:
            sid = _validate_id(sid, "speaker-id")
        except argparse.ArgumentTypeError as error:
            _fail(str(error))
        setattr(a, "_automation_context", context)
        return url, key, sid

    url = supplied_url or os.getenv("SPEAKERAGENT_API_URL")
    sid = supplied_speaker or os.getenv("SPEAKERAGENT_SPEAKER_ID")
    if not (url and key) or (require_speaker and not sid):
        required = "SPEAKERAGENT_API_URL and SPEAKERAGENT_API_KEY"
        if require_speaker:
            required += ", plus SPEAKERAGENT_SPEAKER_ID"
        _fail(f"Set {required}. Passing the key as an argument is discouraged.")
    url = url.rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (getattr(a, "allow_insecure_localhost", False) and is_loopback):
        _fail(
            "SPEAKERAGENT_API_URL must use HTTPS. For local development only, use "
            "http://localhost with --allow-insecure-localhost."
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        _fail("SPEAKERAGENT_API_URL must not contain credentials, a query, or a fragment.")
    if not parsed.hostname:
        _fail("SPEAKERAGENT_API_URL is invalid.")
    if sid:
        try:
            sid = _validate_id(sid, "speaker-id")
        except argparse.ArgumentTypeError as error:
            _fail(str(error))
    return url, key, sid


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as error:
        _fail(f"Cannot read {path}: {error}")
    except json.JSONDecodeError as error:
        _fail(f"Invalid JSON in {path}: line {error.lineno}, column {error.colno}")


def _object_payload(path, allowed_fields, required_fields=()):
    payload = _load_json(path)
    if not isinstance(payload, dict):
        _fail(f"{path} must contain one JSON object.")
    unknown = sorted(set(payload) - set(allowed_fields))
    if unknown:
        _fail(f"Unsupported field(s) in {path}: {', '.join(unknown)}")
    missing = sorted(field for field in required_fields if not payload.get(field))
    if missing:
        _fail(f"Missing required field(s) in {path}: {', '.join(missing)}")
    if "password" in payload or "password_hash" in payload:
        _fail("Passwords are not accepted in profile files.")
    return payload


def _confirm(message, yes=False):
    if yes:
        return
    if not sys.stdin.isatty():
        _fail(f"{message} Re-run with --yes to confirm in non-interactive use.")
    answer = input(f"{message} Type 'yes' to continue: ").strip().lower()
    if answer != "yes":
        _fail("Cancelled.")


def _with_query(url, **params):
    parsed = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v is not None})
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), "")
    )


def _safe_url(url):
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _sanitize_error_message(message, key):
    safe = str(message or "request failed").replace(key, "[redacted]")
    return re.sub(r"sa_(?:test|live)_[A-Za-z0-9_-]+", "[redacted]", safe)


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow redirects only when scheme and network location are unchanged."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(newurl)
        if (old.scheme.lower(), old.netloc.lower()) != (
            new.scheme.lower(),
            new.netloc.lower(),
        ):
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                "authenticated cross-origin redirect blocked",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameOriginRedirectHandler())


def _req(method, url, key, body=None, idempotency_key=None, timeout=30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request_id = str(uuid.uuid4())
    headers = {
        "X-API-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "speakeragent-cli/0.2",
        "X-Request-ID": request_id,
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw or "{}")
    except urllib.error.HTTPError as error:
        try:
            detail = error.read(2048).decode("utf-8", errors="replace")
            parsed = json.loads(detail)
            message = parsed.get("message") or parsed.get("error") or parsed.get("detail")
            if isinstance(message, dict):
                message = message.get("message") or "request failed"
            if not isinstance(message, str):
                message = "request failed"
            message = _sanitize_error_message(message, key)
        except (json.JSONDecodeError, AttributeError):
            message = "request failed"
        _fail(
            f"{method} {_safe_url(url)} -> {error.code}: {message} "
            f"(request_id={request_id})"
        )
    except urllib.error.URLError as error:
        reason = getattr(error, "reason", "network error")
        _fail(
            f"{method} {_safe_url(url)} -> network error: {reason} "
            f"(request_id={request_id})"
        )
    except json.JSONDecodeError:
        _fail(
            f"{method} {_safe_url(url)} -> invalid JSON response "
            f"(request_id={request_id})"
        )


def _podcast_url(base, path, sid, **query):
    return _with_query(f"{base}{path}", speaker_id=sid, **query)


def _redact(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]"
            if (key in SENSITIVE_FIELDS or key.lower() in SENSITIVE_FIELDS_NORMALIZED) and item
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def cmd_podcasts(a):
    url, key, sid = _cfg(a)
    request_url = _podcast_url(
        url,
        "/api/podcasts",
        sid,
        status=a.status,
        triage=a.triage,
        saved="true" if a.saved else None,
    )
    out = _req("GET", request_url, key)
    pods = out.get("podcasts", [])
    if a.json:
        print(json.dumps(pods if a.reveal_sensitive else _redact(pods), indent=2))
        return
    print(f"{len(pods)} podcast(s):")
    for podcast in pods:
        print(
            f"  [{str(podcast.get('Lead Triage', '?')):6}] "
            f"{str(podcast.get('Match Score', '')):>3}  {podcast.get('id')}  "
            f"{str(podcast.get('Podcast Name', ''))[:38]:38}"
        )


def cmd_show(a):
    url, key, sid = _cfg(a)
    result = _req("GET", _podcast_url(url, f"/api/podcasts/{a.id}", sid), key)
    print(json.dumps(result if a.reveal_sensitive else _redact(result), indent=2))


def cmd_status(a):
    url, key, sid = _cfg(a)
    out = _req(
        "PUT",
        _podcast_url(url, f"/api/podcasts/{a.id}/status", sid),
        key,
        {"status": a.status, "updated_by": "speakeragent-cli"},
    )
    print(f"ok - {a.id} -> {out.get('Lead Status', a.status)}")


def cmd_saved(a):
    url, key, sid = _cfg(a)
    _req(
        "PUT",
        _podcast_url(url, f"/api/podcasts/{a.id}/saved", sid),
        key,
        {"saved": a.value},
    )
    print(f"ok - {a.id} saved={str(a.value).lower()}")


def cmd_refresh(a):
    url, key, sid = _cfg(a)
    idempotency_key = str(uuid.uuid4())
    _req(
        "POST",
        _podcast_url(url, f"/api/podcasts/{a.id}/refresh", sid),
        key,
        {"request_id": idempotency_key},
        idempotency_key=idempotency_key,
    )
    print(f"ok - refreshing {a.id}; run show again shortly")


def cmd_email(a):
    url, key, sid = _cfg(a)
    podcast = _req("GET", _podcast_url(url, f"/api/podcasts/{a.id}", sid), key)
    if not a.reveal_sensitive:
        print(
            "Email address and pitch are sensitive. Re-run with --reveal-sensitive "
            "to display them."
        )
        return
    recipient = podcast.get("Contact Email", "")
    subject = podcast.get("Email Subject", "")
    body = podcast.get("Email Draft", "")
    if not body:
        print(f"No pitch yet - run `refresh {a.id}` first.")
        return
    print(f"To:      {recipient}\nSubject: {subject}\n\n{body}")
    print("\nThe Gmail compose URL is not printed because it would expose this content in history.")


def cmd_auth_check(a):
    url, key, sid = _cfg(a, require_speaker=False)
    if _api_key_type(key) == "legacy" and not sid:
        _fail(
            "Set SPEAKERAGENT_API_URL and SPEAKERAGENT_API_KEY, plus "
            "SPEAKERAGENT_SPEAKER_ID. Passing the key as an argument is discouraged."
        )
    result = getattr(a, "_automation_context", None)
    if result is None:
        result = _req(
            "GET",
            _with_query(f"{url}/api/automation-keys/current", speaker_id=sid),
            key,
        )
    result.pop("api_key", None)
    result.pop("key_hash", None)
    result["key_preview"] = (
        f"sa_{_api_key_type(key)}_..."
        if _api_key_type(key) != "legacy"
        else "legacy (hidden)"
    )
    print(json.dumps(result, indent=2))


def cmd_speakers_list(a):
    url, key, _ = _cfg(a, require_speaker=False)
    context = getattr(a, "_automation_context", {})
    if context.get("authorization_model") != "agency_key":
        _fail("`speakers list` requires an agency API key.")
    result = _req("GET", f"{url}/api/automation-keys/current/speakers", key)
    speakers = result.get("speakers", [])
    if a.json:
        print(json.dumps(result, indent=2))
        return
    if not speakers:
        print("No active speaker seats are available.")
        return
    print(f"{'SPEAKER ID':<38} {'NAME':<30} STATUS")
    for speaker in speakers:
        print(
            f"{str(speaker.get('speaker_id') or ''):<38} "
            f"{str(speaker.get('full_name') or ''):<30} "
            f"{str(speaker.get('status') or 'active')}"
        )


def cmd_profile_show(a):
    url, key, sid = _cfg(a)
    profile = _req("GET", f"{url}/api/speaker/{sid}", key)
    safe_profile = {field: profile[field] for field in PROFILE_DISPLAY_FIELDS if field in profile}
    safe_profile["speaker_id"] = profile.get("speaker_id", sid)
    print(json.dumps(safe_profile if a.reveal_sensitive else _redact(safe_profile), indent=2))


def cmd_profile_create(a):
    url, key, _ = _cfg(a, require_speaker=False)
    payload = _object_payload(
        a.from_file,
        PROFILE_CREATE_FIELDS,
        required_fields=("full_name", "email"),
    )
    payload.setdefault("send_welcome_email", False)
    result = _req("POST", f"{url}/api/speakers/register", key, payload)
    print(
        json.dumps(
            {
                "speaker_id": result.get("speaker_id"),
                "status": result.get("status"),
                "message": "Speaker created. Complete billing/account setup before running matches.",
            },
            indent=2,
        )
    )


def cmd_profile_edit(a):
    url, key, sid = _cfg(a)
    payload = _object_payload(a.from_file, PROFILE_UPDATE_FIELDS)
    if not payload:
        _fail("Profile update file contains no fields.")
    result = _req("PUT", f"{url}/api/speaker/{sid}", key, payload)
    print(json.dumps({"speaker_id": sid, "status": "updated", "id": result.get("id")}, indent=2))


def _scout_status(url, key, sid):
    return _req("GET", f"{url}/api/scout/status/{sid}", key)


def _wait_for_scout(url, key, sid, poll_interval, timeout):
    deadline = time.monotonic() + timeout
    while True:
        status = _scout_status(url, key, sid)
        state = status.get("scout_status")
        step = status.get("scout_step")
        progress = status.get("scout_progress_pct")
        print(
            f"scout status={state or 'unknown'} step={step} progress={progress}%",
            file=sys.stderr,
        )
        if state != "Running":
            return status
        if time.monotonic() >= deadline:
            _fail(f"Scout is still running after {timeout} seconds.")
        time.sleep(poll_interval)


def cmd_matches_generate(a):
    url, key, sid = _cfg(a)
    _confirm(
        "Generating matches consumes one monthly scout run and starts background work.",
        a.yes,
    )
    request_url = _with_query(
        f"{url}/api/scout/run", speaker_id=sid, persona_id=a.persona_id
    )
    result = _req("POST", request_url, key, {})
    print(json.dumps(result, indent=2))
    if a.wait:
        final_status = _wait_for_scout(
            url, key, sid, a.poll_interval, a.timeout
        )
        print(json.dumps(final_status, indent=2))


def cmd_matches_status(a):
    url, key, sid = _cfg(a)
    print(json.dumps(_scout_status(url, key, sid), indent=2))


def cmd_billing_show(a):
    url, key, sid = _cfg(a)
    subscription = _req("GET", f"{url}/api/speaker/{sid}/subscription", key)
    profile = _req("GET", f"{url}/api/speaker/{sid}", key)
    plan = profile.get("plan") or {}
    result = {
        "speaker_id": sid,
        "plan": subscription.get("plan") or plan.get("tier") or "Free",
        "billing_source": subscription.get("billing_source"),
        "subscription_status": subscription.get("stripe_subscription_status"),
        "current_period_end": subscription.get("stripe_current_period_end"),
        "cancel_at_period_end": subscription.get("stripe_cancel_at_period_end", False),
        "trial_expires_at": subscription.get("trial_expires_at"),
        "scout_runs": {
            "used": plan.get("scouts_used"),
            "remaining": plan.get("scouts_remaining"),
            "maximum": plan.get("max_scout_runs"),
            "resets_at": plan.get("resets_at"),
        },
        "note": "Credits currently represent monthly scout runs; no generic credit ledger is exposed.",
    }
    print(json.dumps(result, indent=2))


def cmd_voice_samples_list(a):
    url, key, sid = _cfg(a)
    samples = _req("GET", f"{url}/api/speaker/{sid}/voice-samples", key)
    if not a.reveal_sensitive:
        samples = [
            {"id": sample.get("id"), "sample_text": "[redacted]"}
            for sample in samples
        ]
    print(json.dumps(samples, indent=2))


def cmd_voice_samples_set(a):
    url, key, sid = _cfg(a)
    if not a.confirm_own_writing:
        _fail(
            "Voice samples require --confirm-own-writing to attest that confirmed samples "
            "are the speaker's own writing."
        )
    payload = _load_json(a.from_file)
    if isinstance(payload, list):
        payload = {"samples": payload}
    if not isinstance(payload, dict) or set(payload) != {"samples"}:
        _fail(f"{a.from_file} must be a JSON list or an object containing only 'samples'.")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        _fail("At least one voice sample is required.")
    confirmed = 0
    for index, sample in enumerate(samples, 1):
        if not isinstance(sample, dict) or not isinstance(sample.get("sample_text"), str):
            _fail(f"Voice sample {index} requires a string sample_text.")
        unknown = set(sample) - {
            "sample_text", "source_type", "label", "is_own_writing_confirmed"
        }
        if unknown:
            _fail(f"Voice sample {index} has unsupported fields: {', '.join(sorted(unknown))}")
        source_type = sample.get("source_type", "other")
        if source_type not in VOICE_SOURCE_TYPES:
            _fail(
                f"Voice sample {index} source_type must be one of: "
                f"{', '.join(sorted(VOICE_SOURCE_TYPES))}."
            )
        if sample.get("is_own_writing_confirmed") is True:
            confirmed += 1
    if not confirmed:
        _fail("At least one sample must set is_own_writing_confirmed to true.")
    _confirm(
        "This replaces all currently active voice samples and starts voice analysis.",
        a.yes,
    )
    result = _req("POST", f"{url}/api/speaker/{sid}/voice-samples", key, payload)
    print(json.dumps(result, indent=2))


def cmd_voice_status(a):
    url, key, sid = _cfg(a)
    print(json.dumps(_req("GET", f"{url}/api/speaker/{sid}/voice-profile", key), indent=2))


def cmd_voice_preview(a):
    url, key, sid = _cfg(a)
    result = _req(
        "POST",
        f"{url}/api/speaker/{sid}/preview-voice",
        key,
        {},
        timeout=60,
    )
    print(json.dumps(result, indent=2))


def _add_reveal(parser):
    parser.add_argument(
        "--reveal-sensitive",
        action="store_true",
        help="show contact details and pitch content (may be captured by terminal logs)",
    )


def _add_speaker_override(parser):
    parser.add_argument(
        "--speaker-id",
        type=lambda value: _validate_id(value, "speaker-id"),
        default=argparse.SUPPRESS,
        help="agency key: select one authorized speaker seat",
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="speakeragent",
        description="Work your SpeakerAgent.ai podcast leads from the CLI.",
    )
    parser.add_argument("--api-url", help=argparse.SUPPRESS)
    parser.add_argument("--api-key", help=argparse.SUPPRESS)
    parser.add_argument(
        "--speaker-id",
        type=lambda value: _validate_id(value, "speaker-id"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--allow-insecure-localhost",
        action="store_true",
        help="allow HTTP only when the API host is localhost",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    podcasts = sub.add_parser("podcasts", help="list your podcast leads")
    podcasts.add_argument("--status", choices=STATUSES)
    podcasts.add_argument("--triage", choices=TRIAGE_VALUES)
    podcasts.add_argument("--saved", action="store_true")
    podcasts.add_argument("--json", action="store_true")
    _add_speaker_override(podcasts)
    _add_reveal(podcasts)
    podcasts.set_defaults(fn=cmd_podcasts)

    show = sub.add_parser("show", help="show one podcast as JSON")
    show.add_argument("id", type=_validate_id)
    _add_speaker_override(show)
    _add_reveal(show)
    show.set_defaults(fn=cmd_show)

    email = sub.add_parser("email", help="show the drafted pitch")
    email.add_argument("id", type=_validate_id)
    _add_speaker_override(email)
    _add_reveal(email)
    email.set_defaults(fn=cmd_email)

    refresh = sub.add_parser("refresh", help="enrich the host and draft a pitch")
    refresh.add_argument("id", type=_validate_id)
    _add_speaker_override(refresh)
    refresh.set_defaults(fn=cmd_refresh)

    status = sub.add_parser("status", help="set pipeline status")
    status.add_argument("id", type=_validate_id)
    status.add_argument("status", choices=STATUSES)
    _add_speaker_override(status)
    status.set_defaults(fn=cmd_status)

    saved = sub.add_parser("saved", help="set the Saved flag")
    saved.add_argument("id", type=_validate_id)
    saved.add_argument("value", type=_strict_bool)
    _add_speaker_override(saved)
    saved.set_defaults(fn=cmd_saved)

    auth = sub.add_parser("auth", help="verify API-key and speaker access")
    auth_sub = auth.add_subparsers(dest="auth_cmd", required=True)
    auth_check = auth_sub.add_parser(
        "check", help="verify the configured key can access the selected speaker"
    )
    _add_speaker_override(auth_check)
    auth_check.set_defaults(fn=cmd_auth_check)

    speakers = sub.add_parser("speakers", help="list speakers available to an agency API key")
    speakers_sub = speakers.add_subparsers(dest="speakers_cmd", required=True)
    speakers_list = speakers_sub.add_parser("list", help="list active purchased speaker seats")
    speakers_list.add_argument("--json", action="store_true")
    speakers_list.set_defaults(fn=cmd_speakers_list)

    profile = sub.add_parser("profile", help="create, view, or edit a speaker profile")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)
    profile_show = profile_sub.add_parser("show", help="show the configured speaker profile")
    _add_speaker_override(profile_show)
    _add_reveal(profile_show)
    profile_show.set_defaults(fn=cmd_profile_show)
    profile_create = profile_sub.add_parser(
        "create", help="register a new speaker from a JSON profile file"
    )
    profile_create.add_argument("--from", dest="from_file", required=True, metavar="FILE")
    profile_create.set_defaults(fn=cmd_profile_create)
    profile_edit = profile_sub.add_parser(
        "edit", help="update the configured speaker from a JSON profile file"
    )
    profile_edit.add_argument("--from", dest="from_file", required=True, metavar="FILE")
    _add_speaker_override(profile_edit)
    profile_edit.set_defaults(fn=cmd_profile_edit)

    matches = sub.add_parser("matches", help="generate new podcast matches or view scout status")
    matches_sub = matches.add_subparsers(dest="matches_cmd", required=True)
    matches_generate = matches_sub.add_parser(
        "generate", help="consume one scout run and generate new podcast matches"
    )
    matches_generate.add_argument("--persona-id", type=_validate_id)
    matches_generate.add_argument("--wait", action="store_true")
    matches_generate.add_argument("--poll-interval", type=_positive_int, default=5)
    matches_generate.add_argument("--timeout", type=_positive_int, default=900)
    matches_generate.add_argument("--yes", action="store_true", help="confirm quota consumption")
    _add_speaker_override(matches_generate)
    matches_generate.set_defaults(fn=cmd_matches_generate)
    matches_status = matches_sub.add_parser("status", help="show podcast scout progress")
    _add_speaker_override(matches_status)
    matches_status.set_defaults(fn=cmd_matches_status)

    billing = sub.add_parser("billing", help="show subscription and monthly scout allowance")
    billing_sub = billing.add_subparsers(dest="billing_cmd", required=True)
    billing_show = billing_sub.add_parser("show", help="show read-only billing and usage status")
    _add_speaker_override(billing_show)
    billing_show.set_defaults(fn=cmd_billing_show)

    voice = sub.add_parser("voice", help="manage writing samples and preview speaker voice")
    voice_sub = voice.add_subparsers(dest="voice_cmd", required=True)
    voice_samples = voice_sub.add_parser("samples", help="list or replace voice samples")
    voice_samples_sub = voice_samples.add_subparsers(dest="voice_samples_cmd", required=True)
    voice_samples_list = voice_samples_sub.add_parser("list", help="list saved voice samples")
    _add_speaker_override(voice_samples_list)
    _add_reveal(voice_samples_list)
    voice_samples_list.set_defaults(fn=cmd_voice_samples_list)
    voice_samples_set = voice_samples_sub.add_parser(
        "set", help="replace voice samples using a JSON file"
    )
    voice_samples_set.add_argument("--from", dest="from_file", required=True, metavar="FILE")
    voice_samples_set.add_argument("--confirm-own-writing", action="store_true", required=True)
    voice_samples_set.add_argument("--yes", action="store_true", help="confirm replacement")
    _add_speaker_override(voice_samples_set)
    voice_samples_set.set_defaults(fn=cmd_voice_samples_set)
    voice_status = voice_sub.add_parser("status", help="show voice extraction status")
    _add_speaker_override(voice_status)
    voice_status.set_defaults(fn=cmd_voice_status)
    voice_preview = voice_sub.add_parser("preview", help="generate a synthetic voice preview")
    _add_speaker_override(voice_preview)
    voice_preview.set_defaults(fn=cmd_voice_preview)
    return parser


def main():
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
