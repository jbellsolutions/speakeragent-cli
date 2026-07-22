# SpeakerAgent API + CLI

## Install from GitHub

Install the current release directly from GitHub:

```bash
python -m pip install "git+https://github.com/jbellsolutions/speakeragent-cli.git@codex/cli-security-updates"
```

Then run the CLI from any directory:

```bash
speakeragent --help
speakeragent auth check
```

Upgrade to the latest commit on the branch with:

```bash
python -m pip install --upgrade --force-reinstall "git+https://github.com/jbellsolutions/speakeragent-cli.git@codex/cli-security-updates"
```

## Current CLI security controls

The CLI continues to use the existing `X-API-Key` plus `speaker_id` API contract. The current
hardening release adds these client-side protections:

- authenticated requests require HTTPS;
- HTTP is allowed only for an explicit localhost development session using
  `--allow-insecure-localhost`;
- authenticated redirects to another scheme or host are blocked;
- every podcast request, including record reads and writes, includes `speaker_id`;
- `--api-key` is hidden and deprecated because arguments can leak through shell history and process
  listings; use the `SPEAKERAGENT_API_KEY` environment variable;
- IDs, status values, triage values, and Booleans are validated locally;
- contact information and pitch content are redacted unless `--reveal-sensitive` is supplied;
- error messages omit query parameters and include a request ID;
- Gmail compose URLs containing private pitch content are no longer printed.

These controls do not replace backend authorization. For every record request, the API must query by
both record ID and `speaker_id`, and verify that the API key is allowed to access that speaker. The
CLI cannot enforce ownership if the server ignores this check.

Sensitive output now requires an explicit flag:

```bash
python3 speakeragent.py show <id> --reveal-sensitive
python3 speakeragent.py email <id> --reveal-sensitive
```

### Reusing the CLI for multiple speakers

Set `SPEAKERAGENT_SPEAKER_ID` as the default speaker, then override it on any command without changing
the source or API credentials:

```bash
export SPEAKERAGENT_SPEAKER_ID=speaker_default

python3 speakeragent.py podcasts
python3 speakeragent.py podcasts --speaker-id speaker_client_b
python3 speakeragent.py show rec123 --speaker-id speaker_client_b
python3 speakeragent.py status rec123 Contacted --speaker-id speaker_client_b
```

The `--speaker-id` value is included in every request. The API must still verify that the configured
API key is authorized for that speaker.

## Profile, matches, billing, and voice

Create a speaker account from a JSON profile. Passwords are deliberately not accepted in files or
arguments. The new account may require billing/account setup on the website before it can run a scout:

```bash
python3 speakeragent.py profile create --from examples/profile.example.json
```

View or partially update an existing speaker:

```bash
python3 speakeragent.py profile show
python3 speakeragent.py profile show --reveal-sensitive
python3 speakeragent.py profile edit --from examples/profile.example.json
```

Generate new podcast matches. This consumes one monthly scout run, so confirmation is required. Use
`--wait` to poll progress until the backend is no longer running:

```bash
python3 speakeragent.py matches generate
python3 speakeragent.py matches generate --wait --yes
python3 speakeragent.py matches status
```

Show subscription state and monthly scout allowance (the backend does not currently expose a generic
credit ledger):

```bash
python3 speakeragent.py billing show
```

Save writing samples, monitor voice extraction, and generate a synthetic preview. Saving samples
replaces the current active set and requires an explicit authorship attestation:

```bash
python3 speakeragent.py voice samples list
python3 speakeragent.py voice samples list --reveal-sensitive
python3 speakeragent.py voice samples set --from examples/voice-samples.example.json \
  --confirm-own-writing
python3 speakeragent.py voice status
python3 speakeragent.py voice preview
```

Under the current shared-key model, these commands are for trusted/internal operators. The API key
must be bound server-side to the speaker IDs it may access before broad customer distribution.

## Test and production automation keys

The CLI accepts the existing Railway key during migration as well as future customer-specific keys:

```text
sa_test_...   integration and customer testing
sa_live_...   production customer automation
```

All key types continue to use the `X-API-Key` header, so no command changes when the backend begins
issuing customer keys. Configure the complete secret through the environment and verify access to the
selected speaker:

```bash
export SPEAKERAGENT_API_KEY=sa_test_replace_with_complete_key
export SPEAKERAGENT_SPEAKER_ID=speaker_test

python3 speakeragent.py auth check
```

`auth check` calls the API's protected automation-key introspection endpoint. It never prints the key.
Customer keys report `speaker_scope_verified: true` only after the backend verifies the stored key,
status, environment, speaker binding, and scopes. The legacy Railway key remains supported for
internal traffic and reports that speaker scope is not verified. A malformed `sa_test_` or `sa_live_`
key is rejected before any request.

Do not use test keys against production data, commit them to Git, or place them directly in command
arguments. The backend remains responsible for validating key status, expiry, speaker restrictions,
and scopes.

Pull and action your **SpeakerAgent.ai** podcast leads — programmatically (CLI / any agent) or
over the REST API. SpeakerAgent finds podcasts you'd be a great guest on, scores them, and (on
demand) enriches the host + drafts your outreach email. This repo is the **CLI**, the **agent
skill**, and the **API documentation**.

> ⚠️ **Conferences/leads were retired.** The old `/api/leads*` endpoints now return **410 — "use
> the Podcasts section."** The live feature is **Podcasts** (`/api/podcasts*`), documented below.

---

## Auth

All API requests are authenticated two ways at once:

| What | How | Notes |
|------|-----|-------|
| **API key** | `X-API-Key: <key>` request header | A single per-deployment key. Get it from your SpeakerAgent admin. |
| **Tenant** | `speaker_id=<id>` query param | Identifies whose data you're reading. Find it via `POST /api/auth/login`. |

```bash
curl -H "X-API-Key: $SPEAKERAGENT_API_KEY" \
  "$SPEAKERAGENT_API_URL/api/podcasts?speaker_id=$SPEAKERAGENT_SPEAKER_ID"
```

**Base URL:** `https://api-production-d34e.up.railway.app`  *(set as `SPEAKERAGENT_API_URL`)*

> 🔒 Never commit your `X-API-Key`. Keep it in an env var / secret store. The key is an
> account-level credential — treat it like a password.

> 🛣️ **Roadmap — per-speaker OAuth tokens.** A `POST /api/connect/token` (password-gated) +
> `Authorization: Bearer <token>` flow is planned so a third-party app can be scoped to a single
> speaker without holding the shared admin key. Until then, use `X-API-Key` + `speaker_id`.

---

## Quickstart (CLI)

```bash
export SPEAKERAGENT_API_URL=https://api-production-d34e.up.railway.app
export SPEAKERAGENT_API_KEY=<your-key>
export SPEAKERAGENT_SPEAKER_ID=<your-speaker-id>

python3 speakeragent.py podcasts                 # list your podcast leads
python3 speakeragent.py refresh <id>             # enrich the host + draft the pitch email
python3 speakeragent.py email <id>               # print the drafted pitch + a Gmail compose link
python3 speakeragent.py status <id> Contacted    # move it through your pipeline
python3 speakeragent.py saved <id> true          # ♥ save it
```

---

## API reference

### Podcasts

#### `GET /api/podcasts`
List the speaker's podcast leads.

| Query param | Type | Notes |
|-------------|------|-------|
| `speaker_id` | string, **required** | the tenant |
| `status` | string | filter by `Lead Status` (New / Contacted / Replied / Booked / Passed) |
| `triage` | string | filter by `Lead Triage` (RED / YELLOW / GREEN) |
| `saved` | bool | `true` = only ♥ saved; `false` = only unsaved; omit = all |
| `persona_id` | string | filter to a speaker persona |
| `include_inactive` | bool | default `false` (active leads only) |

**Response** `200`:
```json
{ "count": 20, "podcasts": [ { "id": "rec…", "Podcast Name": "…", "Match Score": 83, … } ] }
```

#### `GET /api/podcasts/{id}`
One podcast → `{ "id": "rec…", …fields }`. `404` if not found.

#### `GET /api/podcasts/stats?speaker_id=<id>`
Aggregates → `{ total, by_triage:{RED,YELLOW,GREEN}, by_status:{…}, avg_score, emails_found, emails_verified }`.

#### `PUT /api/podcasts/{id}/status`
Move a lead through the pipeline. **Does not send any email** (safe to set freely).
```json
// body
{ "status": "Contacted" }   // one of: New | Contacted | Replied | Booked | Passed
```

#### `PUT /api/podcasts/{id}/saved`
Toggle the ♥ Saved flag. Body: `{ "saved": true }`.

#### `POST /api/podcasts/{id}/refresh`
**Generate the pitch.** Enriches the host contact (email / LinkedIn) and drafts the outreach
`Email Subject` + `Email Draft`. Runs in the background; re-fetch the lead shortly after.
*(Raw podcasts have no contact/email draft until you do this.)*

#### `POST /api/podcasts/topup`
Promote inactive leads so the "New" column stays stocked.

### Auth

#### `POST /api/auth/login`
```json
// body
{ "email": "you@example.com", "password": "…" }
// 200
{ "status": "ok", "speaker_id": "…", "full_name": "…", "email": "…", "plan": "Pro" }
```
Password is bcrypt-verified server-side; no token is issued (the response carries your `speaker_id`).

#### `POST /api/speakers/register`
Create a speaker account → returns a new `speaker_id`.

### Retired
`GET|PUT /api/leads*` → **410 Gone** ("Conference features are no longer available. Please use the
Podcasts section."). Use `/api/podcasts*`.

---

## Podcast field reference (Airtable display-case)

| Field | Meaning |
|-------|---------|
| `id` | record id (use in `/api/podcasts/{id}` paths) |
| `Podcast Name` | the show |
| `Host Name` | host |
| `Podcast URL` / `Feed URL` | show website / RSS |
| `Match Score` | 0–100 fit score |
| `Lead Triage` | `RED` / `YELLOW` / `GREEN` |
| `The Hook` · `Best Topic` · `CTA` · `Match Reason` | AI pitch angle + why it matched |
| `Lead Status` | New / Contacted / Replied / Booked / Passed (empty until you set it) |
| `Saved` | ♥ flag (0/1) |
| `Reach Estimate` · `Categories` · `Episode Count` · `Publish Frequency` | show metadata |
| **refresh-only** ↓ | *(populated by `POST /{id}/refresh`)* |
| `Contact Email` · `Contact LinkedIn` · `Contact Twitter` · `Contact Bio` | host contact |
| `Email Subject` · `Email Draft` | your drafted outreach |
| `Booking URL` / `Guest Form URL` | where to apply to guest |

---

## CLI command reference

```
speakeragent.py podcasts [--status New] [--triage GREEN|YELLOW|RED] [--saved] [--json]
speakeragent.py show <id>                         # full JSON
speakeragent.py refresh <id>                      # generate the pitch (enrich host + draft email)
speakeragent.py email <id>                        # print the pitch + a Gmail compose URL
speakeragent.py status <id> <New|Contacted|Replied|Booked|Passed>
speakeragent.py saved <id> <true|false>
```
Auth comes from `SPEAKERAGENT_API_URL` / `SPEAKERAGENT_API_KEY` / `SPEAKERAGENT_SPEAKER_ID`
(or `--api-url` / `--api-key` / `--speaker-id` flags). Stdlib-only Python 3 — no install.

## Agent skill
`SKILL.md` registers this as a Claude Code skill (`/speakeragent`): "work your SpeakerAgent
podcast leads." Drop the folder in `~/.claude/skills/speakeragent/`.

## Notes
- **No emails are sent by the API** on a status change — send from your own address using the
  Gmail compose link (`email <id>`).
- Errors: `401` (bad/missing key), `404` (no such podcast), `410` (you hit a retired leads
  endpoint), `400` (missing `speaker_id`).
