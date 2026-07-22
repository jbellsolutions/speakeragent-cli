# SpeakerAgent CLI: Product, Security, and Data Revenue Specification

Status: Draft for review
Owner: SpeakerAgent
Scope: Public CLI, public API contract, and the backend capabilities required to support them
Last updated: 2026-07-20

> Implementation note: `SECURITY_IMPLEMENTATION_PLAN.md` is the authoritative delivery plan for
> authentication, tenant isolation, CLI credential handling, migration, and security verification.
> Where this document differs on implementation order or detail, follow that plan.

## 1. Outcome

Ship a CLI and API that are safe for independent speakers, agencies, and integrations while creating
new revenue from customer-approved workflow features and privacy-preserving market intelligence.

Success means:

- a credential can access only the tenant and operations explicitly granted to it;
- secrets and personal contact data do not leak through arguments, logs, URLs, or default output;
- a new user can authenticate, inspect, and update their podcast pipeline with predictable commands;
- every secondary use of customer or contact data has a documented purpose, retention period, and
  lawful basis;
- revenue comes from paid product value and aggregate insights, never from selling raw personal data,
  customer outreach copy, credentials, or identifiable activity without explicit, revocable consent.

## 2. Current-state findings

This repository contains a standard-library Python CLI and API documentation, but not the API server.
Backend controls therefore require validation in the service repository and deployed environment.

| Priority | Finding | Impact | Required disposition |
|---|---|---|---|
| P0 | One deployment-wide `X-API-Key` is combined with a caller-supplied `speaker_id`. | A leaked key or missing ownership check can expose or modify another tenant. | Replace with scoped, per-user or per-service tokens; enforce tenant ownership server-side on every route. |
| P0 | Record routes (`show`, `status`, `saved`, `refresh`, `email`) identify only a record ID. | Insecure direct object reference if the server looks up records globally. | Resolve records through the authenticated tenant and return `404` for out-of-tenant IDs. |
| P1 | `--api-key` permits secrets in shell history and process listings. | Credential disclosure on shared or managed machines. | Deprecate the flag; use OS keychain, environment variables, or stdin/device authorization. |
| P1 | API URL is unrestricted and redirects use default client behavior. | Keys can be sent over plaintext or forwarded to an unintended host. | Require HTTPS outside localhost and reject cross-origin redirects for authenticated calls. |
| P1 | Full records and Gmail compose URLs can expose contact data and pitch text in terminals, logs, history, or browser telemetry. | Personal-data and confidential-content leakage. | Redact by default; require explicit reveal/copy actions; avoid placing message bodies in URLs. |
| P1 | Mutating commands have no documented idempotency, audit, concurrency, or rate-limit contract. | Duplicate enrichment cost, lost updates, and weak incident investigation. | Add idempotency keys, audit events, optimistic concurrency, and rate-limit headers. |
| P2 | CLI arguments accept arbitrary status, Boolean, IDs, and filter values. | Confusing failures and accidental state changes. | Validate locally with typed choices and stable exit codes. |
| P2 | No version negotiation, retry policy, install packaging, config profiles, or automated tests are present. | Fragile integrations and difficult onboarding. | Add a versioned API, packaged executable, profiles, bounded retries, and contract tests. |

## 3. Users and jobs

1. **Independent speaker:** find suitable shows, generate a pitch, and track outreach without exposing
   their account or contact data.
2. **Agency operator:** manage multiple speakers with explicit delegated access and a complete audit
   trail.
3. **Automation developer:** integrate through stable JSON, scoped service credentials, idempotent
   writes, and documented limits.
4. **SpeakerAgent analyst:** measure product performance using minimized, governed data.
5. **Approved insight customer:** purchase sufficiently aggregated podcast-market trends without
   receiving personal data or customer-confidential information.

## 4. Security architecture

### 4.1 Authentication and authorization

- Use OAuth 2.1 Authorization Code with PKCE for people. The CLI launches a browser or uses a device
  authorization flow and stores refresh tokens in the OS credential store.
- Use separately issued service-account credentials for automation. Never reuse an administrative
  deployment secret in customer clients.
- Access tokens are short-lived (target: 15 minutes), audience-bound, issuer-validated, and contain a
  stable subject plus tenant membership. Refresh tokens rotate and are revocable.
- Define least-privilege scopes: `podcasts:read`, `podcasts:write`, `contacts:read`,
  `enrichment:run`, `analytics:read`, and `account:admin`.
- The server derives permitted tenant IDs from the authenticated principal. A `speaker_id` supplied by
  the client is only a selector within that permitted set, never authorization evidence.
- Every record query includes the authorized tenant predicate. Cross-tenant and nonexistent resources
  both return `404` to reduce enumeration.
- Agency delegation records who granted access, to which speakers, with which scopes, and until when.
  Users can review and revoke grants.
- Administrative support access is time-bound, reason-coded, strongly authenticated, and audited.

### 4.2 API safeguards

- Publish `/v1/` endpoints and an OpenAPI document. Maintain an announced deprecation window.
- Require HTTPS with modern TLS. Reject non-HTTPS base URLs except explicit loopback development.
- Do not follow authenticated cross-origin redirects. Set request timeouts separately for connect and
  response operations.
- Accept an `Idempotency-Key` on enrichment and other cost-incurring POST requests. Cache the result
  per tenant and operation for at least 24 hours.
- Support `ETag`/`If-Match` or a record version on updates to prevent silent lost writes.
- Return structured errors with `code`, safe `message`, `request_id`, and optional field details. Never
  echo credentials, passwords, or unnecessary personal data.
- Apply per-principal and per-tenant rate and spend limits. Return standard rate-limit headers and
  `Retry-After`.
- Validate payload schemas, enum values, lengths, URL schemes, and record identifiers server-side.
- Protect login with throttling, breached-password screening, MFA support, and generic failure text.
- Use encryption in transit and at rest; keep application secrets in a managed secret store with
  rotation and access logging.

### 4.3 CLI safeguards

- Add `speakeragent auth login|status|logout`; store secrets in Keychain, Credential Manager, or
  Secret Service. Configuration files contain only non-secret profile metadata and are permissioned
  to the user.
- Remove `--api-key` from help, warn when used, and remove it in the next major release. A temporary
  `SPEAKERAGENT_ACCESS_TOKEN` remains supported for CI.
- Redact contact email, LinkedIn URL, pitch body, and other sensitive fields in default human-readable
  output. Add `--reveal-sensitive` with an interactive warning; non-interactive use requires an
  additional explicit flag.
- Keep machine output on stdout and diagnostics on stderr. Provide `--json`, `--quiet`, and stable
  documented exit codes.
- Replace Gmail compose URLs containing the whole message with clipboard output, a local mail-client
  handoff, or an explicitly confirmed browser action. Do not print the full URL by default.
- Validate enums and strict Booleans locally. Require `--yes` for expensive refreshes when running
  interactively and show expected credit use before confirmation.
- Use bounded exponential retry only for safe/idempotent operations and transient failures. Never
  blindly retry a mutation without an idempotency key.
- Send a versioned user agent but no analytics identifier unless telemetry is separately enabled.
- Provide signed release artifacts, checksums, reproducible builds where practical, dependency and
  secret scanning, and a security contact/disclosure policy.

### 4.4 Audit and operations

- Record authentication, grant, export, sensitive-field reveal, enrichment, and mutation events with
  actor, tenant, action, target, outcome, timestamp, and request ID. Do not put tokens, passwords,
  pitch bodies, or full contact details in audit logs.
- Make tenant audit history available to account administrators and exportable on paid plans.
- Alert on cross-tenant authorization failures, credential abuse, unusual exports, enrichment spend
  spikes, and administrative access.
- Maintain incident response, credential rotation, backup/restore, and tenant deletion runbooks.
- Set service objectives after baseline measurement; proposed targets are 99.9% monthly API
  availability and 95th-percentile non-enrichment response time under 500 ms.

## 5. Easy-to-work-with CLI and API

### 5.1 Proposed command model

```text
speakeragent auth login
speakeragent profile use <name>
speakeragent podcasts list [filters] [--json]
speakeragent podcasts get <id> [--reveal-sensitive]
speakeragent podcasts refresh <id> [--wait] [--yes]
speakeragent podcasts update <id> --status <status>
speakeragent podcasts save <id> | unsave <id>
speakeragent pitches show <id> [--copy]
speakeragent usage
speakeragent config doctor
```

Requirements:

- package as `speakeragent` through PyPI and provide a single-file release where feasible;
- preserve old command aliases for one major version with warnings;
- support named profiles for agency users without copying credentials into config files;
- add pagination, sorting, field selection, and `--output table|json|jsonl`;
- expose async enrichment as a job resource with state, cost, timestamps, and failure reason;
- generate SDK-friendly OpenAPI examples and include a local mock server or recorded fixtures;
- publish a quickstart that reaches the first successful read in under five minutes;
- add unit tests for parsing/redaction and integration contract tests for authentication, tenant
  isolation, errors, retries, and idempotency.

## 6. Data classification and permitted use

| Class | Examples | Default use | Monetization rule |
|---|---|---|---|
| Secrets | passwords, access/refresh tokens, API keys | Authentication only | Never monetize; never log. |
| Customer confidential | personas, private notes, pitches, pipeline status, campaign results | Deliver the contracted service | Never sell or expose; use for model improvement only with separate explicit opt-in. |
| Personal/contact data | host email, social profiles, bios, speaker identity | Matching and outreach requested by the customer | Do not sell as a list; disclose sources and lawful basis; honor rights and suppression. |
| Licensed source data | podcast metadata from partners/providers | Product features within license | Reuse only as the license permits; track provenance and downstream restrictions. |
| Product telemetry | feature events, latency, errors | Operations and product improvement | Aggregate for internal use; external use requires notice, controls, and thresholding. |
| De-identified aggregates | category demand, response-rate bands, regional trends | Benchmarks and insights | Monetizable only after privacy review and minimum cohort thresholds. |
| Public data | public feeds and show pages | Discovery and matching | Monetizable subject to source terms, provenance, accuracy, and applicable law. |

The data inventory is authoritative. Each field must have an owner, source, purpose, lawful basis,
retention period, residency, processor list, and deletion behavior. Collection is minimized to what a
documented product purpose requires.

## 7. Privacy-safe revenue plan

Prioritize products that customers pay for because they improve outcomes:

1. **Pro workflow subscription:** more personas, saved searches, advanced filters, outreach tracking,
   CRM export, and higher enrichment allowance.
2. **Agency tier:** delegated multi-speaker access, team roles, approval flows, audit exports, usage
   controls, and consolidated billing.
3. **Usage-based enrichment:** transparently priced contact enrichment and pitch generation with a
   preflight cost, idempotency, monthly caps, and dispute records.
4. **Outcome analytics:** private benchmarks comparing a customer's funnel against cohorts, shown
   only where aggregation thresholds are met.
5. **Market intelligence:** subscription reports or an API for category momentum, show activity,
   audience bands, and anonymized booking trends.
6. **Sponsored discovery:** clearly labeled placements that never change organic fit scores and use
   only user-selected targeting; no sensitive-trait targeting.
7. **Partner referrals:** opt-in, disclosed referral links for relevant services, with no data transfer
   beyond what the user affirmatively submits.

### 7.1 Aggregate release standard

Before external release of an insight:

- exclude direct identifiers and free text;
- use cohorts of at least 20 independent customers and apply stricter thresholds for sparse or
  sensitive slices;
- suppress or coarsen small cells, rare combinations, exact timestamps, and outliers;
- prevent differencing attacks across report versions and limit high-dimensional queries;
- require a documented re-identification-risk review and contractual prohibition on
  re-identification;
- consider differential privacy for interactive or repeated-query analytics;
- publish methodology, coverage limitations, and whether a metric is observed, inferred, or modeled.

Raw contact lists, identifiable conversion histories, private pitches, and tenant-level activity are
explicitly out of scope for sale or licensing.

### 7.2 Consent and controls

- Separate required processing from optional analytics, model improvement, sponsored discovery, and
  partner sharing. No bundled consent or pre-checked boxes.
- Record the notice version, purpose, actor, timestamp, and withdrawal for every opt-in.
- Make withdrawal as easy as enrollment and stop future optional use promptly.
- Provide access, correction, export, deletion, objection, and suppression workflows. Propagate
  deletion to processors and derived datasets according to documented deadlines.
- Maintain a global outreach suppression list using a privacy-preserving representation where
  feasible. Suppression data is used only to prevent contact and is retained for that purpose.
- Complete legal review for each launch jurisdiction, including controller/processor roles,
  marketing and scraping rules, data-broker registration where applicable, cross-border transfers,
  and vendor agreements. This specification is a product requirement, not legal advice.

## 8. Metrics and guardrails

### Product and revenue

- activation: authenticated account with first successful podcast read;
- time to first value and CLI command success rate;
- paid conversion, expansion revenue, gross margin per enrichment, and churn;
- outreach funnel metrics, computed for the customer first and aggregated only under the release
  standard;
- insight-product renewal and reported usefulness.

### Trust and safety

- zero confirmed cross-tenant disclosures;
- percentage of routes covered by automated authorization tests (target: 100%);
- credential revocation time and mean time to detect/respond;
- personal-data deletion completion within the published service level;
- opt-in and withdrawal rates by purpose, monitored for deceptive design;
- aggregate releases passing privacy review (target: 100%);
- sensitive values detected in application logs (target: zero).

Revenue targets never override privacy thresholds, consent, suppression, source licenses, or tenant
isolation. Product owners cannot waive these controls without documented security, privacy, and legal
approval.

## 9. Delivery plan and acceptance criteria

### Phase 0: validate and contain (0-2 weeks)

- inventory every backend route, datastore, processor, credential, and data field;
- add automated tests proving a credential from tenant A cannot read, mutate, enrich, or infer tenant
  B's records;
- confirm record-level authorization and patch any global record lookup;
- rotate the shared deployment key and stop distributing it to new clients;
- redact secrets and personal data from logs and document incident-response ownership;
- verify source licenses and pause any secondary use lacking a documented basis.

**Exit:** no known cross-tenant path; shared-key exposure is contained; data inventory and owners are
approved.

### Phase 1: secure public beta (2-6 weeks)

- release scoped user and service authentication, OS-keychain CLI login, `/v1`, structured errors,
  rate limits, and audit events;
- add HTTPS/redirect enforcement, safe output defaults, input validation, idempotent enrichment, and
  signed packaged releases;
- publish threat model, privacy notice, retention schedule, subprocessors, security contact, and
  migration guide.

**Exit:** independent security review has no open critical/high issues; authorization contract tests
cover all routes; a new user completes the quickstart in under five minutes.

### Phase 2: paid workflow products (6-10 weeks)

- launch Pro and Agency entitlements, usage meters, spend caps, billing reconciliation, and customer
  audit/export controls;
- provide private outcome analytics and clearly disclose calculation methodology.

**Exit:** entitlements are enforced server-side; usage is reconcilable per tenant; billing cannot be
duplicated by request retries.

### Phase 3: aggregate insights (10+ weeks)

- build a governed aggregation pipeline separated from production serving data;
- apply cohort thresholds, suppression, privacy review, lineage, deletion propagation, and release
  versioning;
- pilot with synthetic or historical aggregates that meet the approved use and licensing rules.

**Exit:** privacy, security, legal, and data-source reviews approve the exact dataset and product;
re-identification testing passes; customers have the promised controls.

## 10. Launch blockers and open decisions

Launch blockers:

- any API route authorizes with `speaker_id` rather than authenticated tenant membership;
- a customer client requires the shared administrative key;
- secrets or sensitive fields appear in routine logs or default CLI output;
- enrichment charges can duplicate after retry;
- a monetized dataset lacks provenance, purpose, retention, licensing, or privacy approval.

Decisions needed:

1. Supported identity provider and whether device authorization is available.
2. Agency role model and delegation lifetime.
3. Jurisdictions and customer segments for the first release.
4. Podcast/contact data providers and their resale/derived-data license terms.
5. Default retention periods for raw contact data, pitches, telemetry, and audit events.
6. Pricing and included enrichment units for Pro and Agency tiers.
7. Minimum aggregation thresholds after empirical re-identification testing.

## 11. Definition of done

The initiative is complete when the Phase 1 acceptance criteria are met for the secure CLI/API and
the selected revenue product has met its corresponding Phase 2 or Phase 3 criteria. Documentation
alone does not satisfy tenant isolation, data governance, or privacy requirements; each control must
have an owner, implementation evidence, and a passing verification artifact.
