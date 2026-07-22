---
name: speakeragent
description: Pull and action your SpeakerAgent.ai PODCAST leads (shows to pitch yourself onto) from the CLI or any agent. List your podcasts, generate the pitch (enrich host + draft email), get a Gmail compose link, save/heart, and sync status back. Use when the user mentions SpeakerAgent, podcast-guesting outreach, or wants to work their SpeakerAgent pipeline programmatically with their own API key.
---

# SpeakerAgent CLI (Podcasts)

Work your **SpeakerAgent.ai** podcast leads from the terminal or any agent. (Conferences/leads were
retired → 410; **Podcasts** is the live feature.) Multi-tenant by `speaker_id`; auth is a single
`X-API-Key`. Anyone can use this with their own key.

## Setup
```bash
export SPEAKERAGENT_API_KEY=sa_live_...  # key from the website's API / CLI page
```

## Commands
```bash
CLI=~/.claude/skills/speakeragent/speakeragent.py

python3 $CLI podcasts [--status New] [--triage GREEN|YELLOW|RED] [--saved] [--json]  # list
python3 $CLI show <id>                                       # one podcast, full JSON
python3 $CLI refresh <id>                                    # generate the pitch (enrich host + draft email)
python3 $CLI email <id>                                      # print the drafted pitch + a Gmail compose URL
python3 $CLI status <id> <New|Contacted|Replied|Booked|Passed>
python3 $CLI saved <id> <true|false>                         # ♥ save / unsave
```

## Additional workflow commands

```bash
python3 $CLI auth check                                      # verify key + speaker access
python3 $CLI profile show [--reveal-sensitive]
python3 $CLI profile create --from <profile.json>
python3 $CLI profile edit --from <profile.json>
python3 $CLI matches generate [--persona-id <id>] [--wait] [--yes]
python3 $CLI matches status
python3 $CLI billing show
python3 $CLI voice samples list [--reveal-sensitive]
python3 $CLI voice samples set --from <samples.json> --confirm-own-writing [--yes]
python3 $CLI voice status
python3 $CLI voice preview
```

Match generation consumes one monthly scout run. Saving voice samples replaces the active sample set,
requires an authorship attestation, and starts asynchronous extraction. Billing is read-only and
reports the subscription plus monthly scout allowance; there is no generic credit ledger today.

## Notes
- **Raw podcasts have no Contact Email / Email Draft until `refresh` runs** — refresh enriches the
  host + drafts the outreach email; then `email <id>` has content.
- Setting status does **not** auto-send any email (safe). Send from your own address via the Gmail link.
- Fields (Airtable display-case): `Podcast Name`, `Host Name`, `Contact Email`, `Contact LinkedIn`,
  `The Hook`, `Best Topic`, `Email Subject`, `Email Draft`, `Match Score`, `Lead Triage`, `Lead
  Status`, `Saved`, `Podcast URL`.
- Endpoints: `GET /api/podcasts`, `GET /api/podcasts/{id}`, `PUT /{id}/status`, `PUT /{id}/saved`,
  `POST /{id}/refresh`.
