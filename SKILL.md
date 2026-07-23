---
name: speakeragent
description: Manage a customer's SpeakerAgent podcast-guesting pipeline through the installed SpeakerAgent CLI. Use when the user asks to review or summarize podcast matches, inspect a podcast or pitch, generate new matches, enrich a lead, update pipeline status or saved state, view profile/billing/voice status, or manage owned writing samples. Require the customer's scoped API key and preserve confirmation gates for credit-consuming, destructive, or sensitive actions.
---

# SpeakerAgent

Use the installed `speakeragent` command. Do not call private backend endpoints directly when the CLI
supports the requested action.

## Install or upgrade the CLI

Before first use in a new environment, or when the installed CLI may be outdated, upgrade pip and
install the latest approved CLI build from GitHub:

```bash
python -m pip install --upgrade pip
python -m pip install --upgrade --force-reinstall "git+https://github.com/jbellsolutions/speakeragent-cli.git@codex/cli-security-updates"
speakeragent --help
```

Stop if installation or the verification command fails. Do not install an unapproved fork or branch.

## Authenticate

Require `SPEAKERAGENT_API_KEY` in the execution environment. Never ask the user to paste the key into
chat, print it, or pass it as a command argument.

Run this before the first operation:

```bash
speakeragent auth check
```

Stop if authentication fails. The key selects the approved test or live API and its owned speaker
automatically; do not request or override an API URL or speaker ID.

## Choose the workflow

Prefer JSON for analysis:

```bash
speakeragent podcasts --json
speakeragent podcasts --status New --json
speakeragent podcasts --triage GREEN --json
speakeragent show <podcast-id>
```

Keep sensitive data redacted unless the user explicitly asks to see contact or pitch content. Only
then use `--reveal-sensitive`:

```bash
speakeragent show <podcast-id> --reveal-sensitive
speakeragent email <podcast-id> --reveal-sensitive
```

Summarize matches using podcast ID, name, match score, triage, topic, and relevance. Do not invent
missing contact details, scores, or pitch content.

## Perform controlled actions

Treat these as changes and confirm the exact target when the user's instruction is ambiguous:

```bash
speakeragent status <podcast-id> <New|Contacted|Replied|Booked|Passed>
speakeragent saved <podcast-id> <true|false>
speakeragent refresh <podcast-id>
speakeragent profile edit --from <profile.json>
```

`refresh` may invoke paid enrichment services. It enriches and drafts content but does not send an
email. Status changes also do not send email.

Match generation consumes one monthly scout run. Explain this and obtain confirmation unless the
user already explicitly requested the run:

```bash
speakeragent matches status
speakeragent matches generate --wait --yes
```

Use `--persona-id <id>` only when the user selected a specific persona.

Replacing voice samples is destructive and requires confirmation that the samples are the user's own
writing:

```bash
speakeragent voice samples list
speakeragent voice samples set --from <samples.json> --confirm-own-writing --yes
speakeragent voice status
speakeragent voice preview
```

Do not add `--confirm-own-writing` unless the user has made that attestation.

## Inspect account state

Use read-only commands without additional confirmation:

```bash
speakeragent profile show
speakeragent billing show
speakeragent matches status
speakeragent voice status
```

If a command returns `403`, explain which permission is missing. Do not work around key scopes. If it
returns `401`, ask the user to replace or recreate the key without sharing it in chat.

## Report results

Lead with the outcome. For writes, state the podcast ID and resulting status or saved value. For
background work, report that it started and use the relevant status command when the user asked to
wait. Never claim that outreach was sent; this CLI does not send email.
