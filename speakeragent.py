#!/usr/bin/env python3
"""speakeragent — pull + action your SpeakerAgent.ai PODCAST leads from any agent/CLI.

(Conferences/leads were retired; the live feature is Podcasts.) Auth (env, or flags):
SPEAKERAGENT_API_URL, SPEAKERAGENT_API_KEY, SPEAKERAGENT_SPEAKER_ID. Multi-tenant by
speaker_id; the X-API-Key is your deployment key. Stdlib only.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _cfg(a):
    url = a.api_url or os.getenv("SPEAKERAGENT_API_URL")
    key = a.api_key or os.getenv("SPEAKERAGENT_API_KEY")
    sid = a.speaker_id or os.getenv("SPEAKERAGENT_SPEAKER_ID")
    if not (url and key):
        sys.exit("Set SPEAKERAGENT_API_URL + SPEAKERAGENT_API_KEY (and SPEAKERAGENT_SPEAKER_ID), "
                 "or pass --api-url/--api-key/--speaker-id.")
    return url.rstrip("/"), key, sid


def _req(method, url, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"X-API-Key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url} -> {e.code}: {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        sys.exit(f"{method} {url} -> {e}")


def cmd_podcasts(a):
    url, key, sid = _cfg(a)
    if not sid:
        sys.exit("podcasts needs SPEAKERAGENT_SPEAKER_ID (or --speaker-id).")
    q = {"speaker_id": sid}
    if a.status:
        q["status"] = a.status
    if a.triage:
        q["triage"] = a.triage
    if a.saved:
        q["saved"] = "true"
    out = _req("GET", f"{url}/api/podcasts?{urllib.parse.urlencode(q)}", key)
    pods = out.get("podcasts", [])
    if a.json:
        print(json.dumps(pods, indent=2))
        return
    print(f"{len(pods)} podcast(s):")
    for p in pods:
        print(f"  [{str(p.get('Lead Triage', '?')):6}] {str(p.get('Match Score', '')):>3}  "
              f"{p.get('id')}  {str(p.get('Podcast Name', ''))[:38]:38}  — {p.get('Host Name', '')}")


def cmd_show(a):
    url, key, _ = _cfg(a)
    print(json.dumps(_req("GET", f"{url}/api/podcasts/{a.id}", key), indent=2))


def cmd_status(a):
    url, key, _ = _cfg(a)
    out = _req("PUT", f"{url}/api/podcasts/{a.id}/status", key,
               {"status": a.status, "updated_by": "speakeragent-cli"})
    print(f"ok — {a.id} -> {out.get('Lead Status', a.status)}")


def cmd_saved(a):
    url, key, _ = _cfg(a)
    val = a.value.lower() in ("true", "1", "yes", "y")
    _req("PUT", f"{url}/api/podcasts/{a.id}/saved", key, {"saved": val})
    print(f"ok — {a.id} saved={val}")


def cmd_refresh(a):
    url, key, _ = _cfg(a)
    _req("POST", f"{url}/api/podcasts/{a.id}/refresh", key, {})
    print(f"ok — refreshing {a.id} (enriches the host + drafts the pitch; re-show in ~a moment)")


def cmd_email(a):
    url, key, _ = _cfg(a)
    p = _req("GET", f"{url}/api/podcasts/{a.id}", key)
    to, su, body = p.get("Contact Email", ""), p.get("Email Subject", ""), p.get("Email Draft", "")
    if not body:
        print("No pitch yet — run `refresh %s` first to enrich the host + draft the email.\n" % a.id)
    print(f"To:      {to}\nSubject: {su}\n\n{body}\n")
    if to:
        gmail = "https://mail.google.com/mail/?view=cm&fs=1&" + urllib.parse.urlencode(
            {"to": to, "su": su, "body": body})
        print(f"Gmail compose: {gmail}")


def main():
    p = argparse.ArgumentParser(prog="speakeragent",
                                description="Work your SpeakerAgent.ai podcast leads from the CLI.")
    p.add_argument("--api-url")
    p.add_argument("--api-key")
    p.add_argument("--speaker-id")
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("podcasts", help="list your podcast leads")
    pl.add_argument("--status")
    pl.add_argument("--triage")
    pl.add_argument("--saved", action="store_true")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(fn=cmd_podcasts)
    ps = sub.add_parser("show", help="show one podcast (json)")
    ps.add_argument("id")
    ps.set_defaults(fn=cmd_show)
    pe = sub.add_parser("email", help="print the drafted pitch + a Gmail compose link")
    pe.add_argument("id")
    pe.set_defaults(fn=cmd_email)
    pr = sub.add_parser("refresh", help="generate the pitch (enrich host + draft email)")
    pr.add_argument("id")
    pr.set_defaults(fn=cmd_refresh)
    pu = sub.add_parser("status", help="set status (New/Contacted/Replied/Booked/Passed)")
    pu.add_argument("id")
    pu.add_argument("status")
    pu.set_defaults(fn=cmd_status)
    pv = sub.add_parser("saved", help="set the Saved flag (true/false)")
    pv.add_argument("id")
    pv.add_argument("value")
    pv.set_defaults(fn=cmd_saved)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
