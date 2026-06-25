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
export SPEAKERAGENT_API_URL=https://api-production-d34e.up.railway.app  # your SpeakerAgent API base
export SPEAKERAGENT_API_KEY=...                                        # your deployment X-API-Key
export SPEAKERAGENT_SPEAKER_ID=...                                     # your speaker account id
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

## Notes
- **Raw podcasts have no Contact Email / Email Draft until `refresh` runs** — refresh enriches the
  host + drafts the outreach email; then `email <id>` has content.
- Setting status does **not** auto-send any email (safe). Send from your own address via the Gmail link.
- Fields (Airtable display-case): `Podcast Name`, `Host Name`, `Contact Email`, `Contact LinkedIn`,
  `The Hook`, `Best Topic`, `Email Subject`, `Email Draft`, `Match Score`, `Lead Triage`, `Lead
  Status`, `Saved`, `Podcast URL`.
- Endpoints: `GET /api/podcasts`, `GET /api/podcasts/{id}`, `PUT /{id}/status`, `PUT /{id}/saved`,
  `POST /{id}/refresh`.
