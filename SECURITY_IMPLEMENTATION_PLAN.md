# SpeakerAgent Security Implementation Plan

Status: Long-term plan; identity creation deferred for the current hardening release
Date: 2026-07-21
Scope: SpeakerAgent API, CLI, authentication, tenant isolation, personal data, and operations

> Current implementation decision: keep the existing shared API key plus `speaker_id` contract for
> now. The immediate controls that work with this model are implemented and tracked in the repository.
> Sections about User, Tenant, Membership, OAuth/device login, and service accounts are deferred, not
> considered complete. Backend record-level authorization remains mandatory during the interim.

## 1. Security goal in normal terms

Each user should log in with their own account. The API should determine which speaker records that
account may access. A user must never gain access merely by changing a `speaker_id` or podcast record
ID in a command.

The CLI should not hold a shared administrative API key. It should receive a short-lived user token,
keep the longer-lived login credential in the operating system's secure credential store, hide
personal contact information by default, and give the backend enough information to audit important
actions.

## 2. The current problem

The current API contract combines:

```text
X-API-Key: one shared deployment key
speaker_id: a value supplied by the caller
```

This is unsafe as a public customer authentication model. The shared key proves only that the caller
knows a deployment secret. A `speaker_id` says which account the caller wants; it does not prove that
the caller owns that account.

Several record-level CLI commands send only a podcast record ID:

```text
GET  /api/podcasts/{id}
PUT  /api/podcasts/{id}/status
PUT  /api/podcasts/{id}/saved
POST /api/podcasts/{id}/refresh
```

If the backend retrieves those records globally, changing the ID could read or modify another
customer's data. The backend is not in this repository, so this behavior must be tested in the API
code and deployment rather than assumed to be safe.

## 3. Target design

```text
User
  -> speakeragent auth login
  -> browser/device login over HTTPS
  -> short-lived access token
  -> SpeakerAgent API
  -> token identity and tenant membership checked
  -> record queried inside an authorized tenant
  -> response returns only permitted fields
```

The central rule is:

> Resource IDs locate data; authenticated membership authorizes access.

Neither `speaker_id`, a podcast ID, nor possession of a URL is authorization.

## 4. Required backend changes

### 4.1 Identity model

Create these concepts in the backend:

| Entity | Purpose |
|---|---|
| User | One human identity with a stable internal ID and verified login methods |
| Tenant | A customer workspace that owns speakers, podcast leads, pitches, and usage |
| Membership | Connects a user to a tenant with a role and status |
| Speaker | A profile owned by exactly one tenant |
| Service account | A non-human identity for approved automation |
| Grant | Optional time-bound access to selected speakers for an agency or collaborator |

Initial roles:

- `owner`: billing, members, credentials, exports, and all tenant data;
- `admin`: members and all workflow data, but no ownership transfer;
- `operator`: create and update speaker campaigns and enrich leads;
- `viewer`: read non-secret campaign data only.

Permissions should be represented as backend actions such as `podcasts.read`, `podcasts.update`,
`contacts.read`, `enrichment.run`, `speakers.manage`, and `billing.manage`. Routes check actions, not
role names, so roles can evolve without rewriting every controller.

### 4.2 Authentication

For people:

- use an established identity provider or well-maintained authentication framework;
- use Authorization Code with PKCE for browser login or Device Authorization for terminal-only
  login;
- issue access tokens lasting approximately 15 minutes;
- rotate refresh tokens after use and revoke the previous token;
- support logout, session listing, remote revocation, password reset, and MFA;
- validate token signature, issuer, audience, expiry, and token type on every API request.

For automation:

- issue a separate service account per integration;
- show its secret once and store only a secure hash where opaque secrets are used;
- restrict it to selected tenant permissions and, where needed, selected speakers;
- allow expiry, rotation, last-used visibility, and immediate revocation;
- never permit a service credential to log into the administrative web interface.

The existing shared `X-API-Key` becomes an internal deployment secret only. It is removed from public
documentation and customer CLI setup.

### 4.3 Tenant isolation

Every authenticated request builds an authorization context:

```text
principal_id
principal_type
permitted_tenant_ids
selected_tenant_id
permissions
request_id
```

Every database access to tenant-owned data includes the selected tenant:

```sql
SELECT *
FROM podcasts
WHERE tenant_id = :authorized_tenant_id
  AND id = :podcast_id;
```

Do not retrieve a record globally and check ownership afterward. Tenant filtering should live in a
shared repository/data-access layer so a new endpoint cannot easily forget it.

Additional requirements:

- speaker records include a non-null `tenant_id` foreign key;
- podcast leads, pitches, enrichment jobs, usage events, exports, and audit records include the
  tenant relationship;
- create/update operations ignore tenant IDs from request bodies and assign the authenticated tenant;
- out-of-tenant and nonexistent record IDs both return `404`;
- caches, background jobs, object-storage keys, search indexes, and analytics queries carry the
  tenant boundary too;
- database row-level security should be considered as a second layer, but never as a substitute for
  application authorization tests.

### 4.4 API contract

Introduce versioned endpoints:

```text
GET    /v1/me
GET    /v1/tenants
POST   /v1/auth/device                 # if device login is selected
GET    /v1/speakers
POST   /v1/speakers
PATCH  /v1/speakers/{speaker_id}
GET    /v1/podcasts
GET    /v1/podcasts/{podcast_id}
PATCH  /v1/podcasts/{podcast_id}
POST   /v1/podcasts/{podcast_id}/enrichment-jobs
GET    /v1/enrichment-jobs/{job_id}
GET    /v1/usage
```

The token selects the allowed tenants. An optional `X-SpeakerAgent-Tenant` header may select one
tenant when an agency user belongs to several, but the backend validates membership. It is never
trusted by itself.

API safeguards:

- accept only HTTPS except for explicit loopback development;
- reject authenticated redirects to a different origin;
- validate all payloads, enums, IDs, lengths, and URL schemes;
- use `Idempotency-Key` for enrichment and billable operations;
- use record versions or `ETag`/`If-Match` for conflicting updates;
- return structured errors containing a safe code, message, and request ID;
- apply limits per user/service account and per tenant;
- never include tokens, passwords, full request headers, or pitch bodies in errors or logs.

### 4.5 Personal-data controls

Classify at minimum:

- secrets: passwords, access tokens, refresh tokens, provider keys;
- customer confidential: speaker bios, pitches, notes, pipeline results;
- contact data: host email addresses, social profiles, biographies;
- ordinary metadata: podcast name, public feed, categories, published episodes;
- operational data: timestamps, request IDs, latency, safe usage counters.

Requirements:

- encrypt data in transit and at rest;
- keep provider and signing secrets in a managed secret store;
- define retention for each class and automatically delete expired data;
- support tenant export and deletion, including downstream processors;
- record the source and retrieval date of contact data;
- keep a suppression mechanism so a contact's deletion or no-contact request is not undone by later
  enrichment;
- prevent raw pitches, contact details, and credentials from entering telemetry or model-training
  datasets;
- require separate, explicit consent before using customer content for model improvement.

## 5. Required CLI changes

### 5.1 Login and credential storage

Add:

```text
speakeragent auth login
speakeragent auth status
speakeragent auth sessions
speakeragent auth logout
```

Login opens the trusted authorization page or starts a device flow. The CLI stores the refresh token
in Windows Credential Manager, macOS Keychain, or Linux Secret Service. A configuration file may
store the API URL, selected tenant, output preference, and profile name, but never a refresh token or
password.

For CI, accept a short-lived token from `SPEAKERAGENT_ACCESS_TOKEN`. Do not support passwords on the
command line. Deprecate `--api-key`, remove it from examples immediately, warn when it is used during
the migration, and delete it in the next major CLI version.

### 5.2 Safe output

- default `podcasts list` output shows show name, fit score, status, and a masked host identity;
- default `podcasts get` masks contact email and omits the full pitch body;
- `--reveal-sensitive` requires an explicit action and generates an audit event;
- non-interactive sensitive output requires both `--reveal-sensitive` and `--yes`;
- JSON output follows the same redaction rule rather than assuming machine output is private;
- diagnostics go to stderr and never print authorization headers or full authenticated URLs;
- replace Gmail compose URLs containing pitch text with clipboard output or a confirmed handoff.

### 5.3 Command safety and reliability

- validate status, triage, Boolean values, URLs, and identifier formats before sending;
- display the credit cost and require confirmation before billable enrichment;
- attach an idempotency key to billable requests and reuse it when retrying;
- retry only safe requests and idempotent mutations after transient failures;
- use short connect timeouts and a bounded total timeout;
- send a versioned user agent and request ID without a persistent analytics identifier by default;
- use stable exit codes for authentication, authorization, validation, rate limit, conflict, and
  network failures.

## 6. Audit and detection

Audit these events:

- login success/failure, MFA and token revocation;
- membership, role, grant, and service-account changes;
- contact reveal and bulk export;
- enrichment request, result, credit charge, and reversal;
- speaker/profile change and podcast status change;
- administrative support access and tenant deletion.

Each event contains timestamp, request ID, actor, tenant, action, target type/ID, outcome, and safe
reason. It must not contain passwords, tokens, full emails, contact payloads, or pitch bodies.

Alert on:

- repeated cross-tenant or sequential-ID access attempts;
- unusual contact reveals or exports;
- sudden enrichment or billing spikes;
- service credentials used from unexpected locations where signals are reliable;
- administrative access outside an approved support session;
- secret patterns or personal data detected in logs.

## 7. Delivery order

### Phase 0: emergency verification and containment (days 1-5)

1. Inventory all backend routes, data stores, queues, caches, storage buckets, and background jobs.
2. Write two test tenants with overlapping-looking data and attempt every read/write route across
   tenants.
3. Patch all record access to filter by the authenticated tenant.
4. Search logs and source history for the shared API key and rotate it.
5. Stop issuing the shared key to new users and remove it from public examples.
6. Add request-body and header redaction to application and infrastructure logs.

Exit criteria:

- no known cross-tenant access path;
- shared key rotated and distribution stopped;
- every existing endpoint has an assigned owner and authorization test;
- no secret or raw sensitive payload appears in newly generated logs.

### Phase 1: identity and authorization foundation (weeks 2-3)

1. Implement User, Tenant, Membership, Speaker ownership, and permission models.
2. Integrate the chosen identity system and validate tokens in one shared middleware layer.
3. Implement scoped service accounts for automation.
4. Add tenant-scoped data repositories and migrate existing records to a verified tenant.
5. Add authorization context and audit events.
6. Add `/v1/me`, tenant selection, and session/revocation endpoints.

Exit criteria:

- 100% of tenant-owned routes use shared tenant-scoped data access;
- negative authorization tests pass for every role, route, and resource type;
- disabling a user, membership, session, or service account blocks new access promptly;
- no production record has an unknown or nullable tenant owner.

### Phase 2: secure CLI beta (weeks 3-5)

1. Add browser/device login and OS credential storage.
2. Add token refresh, logout, session display, and tenant/profile selection.
3. Add safe output defaults and explicit sensitive reveal.
4. Add HTTPS and redirect enforcement, validation, stable errors, timeouts, and safe retries.
5. Add idempotent enrichment confirmation and usage display.
6. Package signed releases and publish checksums plus a security contact.

Exit criteria:

- a new user completes login without copying a shared key;
- CLI secrets do not appear in config files, shell history, process arguments, or normal logs;
- cross-origin redirects cannot receive an authorization token;
- routine list/get commands do not expose contact details or pitch bodies by default.

### Phase 3: migration and shared-key removal (weeks 5-7)

1. Release the secure CLI while temporarily accepting both authentication systems.
2. Notify existing users and provide a login-based migration command.
3. Measure only counts of remaining legacy requests; never log legacy keys.
4. Make the legacy system read-only after the announced migration window.
5. Revoke the customer-facing shared key and remove legacy code and documentation.

Exit criteria:

- no customer workflow depends on the shared key;
- old credentials are revoked and cannot access `/v1`;
- rollback does not re-enable cross-tenant authorization;
- support and incident runbooks reflect the new system.

### Phase 4: independent verification and hardening (weeks 7-9)

1. Threat-model authentication, tenant isolation, enrichment, billing, exports, and deletion.
2. Conduct an independent application and API security assessment.
3. Add dependency, static analysis, secret scanning, and signed release checks to CI.
4. Test backup restoration, token/signing-key rotation, tenant deletion, and incident response.
5. Resolve all critical and high findings before broad release.

Exit criteria:

- no open critical or high security finding;
- restore, rotation, revocation, and deletion exercises have evidence and owners;
- alerts reach an on-call owner and incident handling has been rehearsed.

## 8. Test matrix

Every tenant-owned endpoint must pass these cases:

| Test | Expected result |
|---|---|
| No token | `401` |
| Expired, wrong-audience, or invalid token | `401` |
| Valid user without tenant membership | `404` or `403` according to the resource contract |
| Tenant A requests Tenant B record ID | `404` |
| Viewer attempts mutation or contact reveal | `403` |
| Operator attempts billing/member administration | `403` |
| Disabled membership or revoked session | denied |
| Request body supplies a different tenant ID | ignored/rejected; never reassigned |
| Background job receives another tenant's resource | job fails without disclosure or charge |
| Cached Tenant B ID requested by Tenant A | no cache hit or disclosure |
| Duplicate enrichment idempotency key | one job and one charge |
| Authenticated cross-origin redirect | redirect rejected; no token forwarded |
| Sensitive output without explicit reveal | redacted |
| Export/delete request | authorized, audited, complete, and scoped |

Tests must include list, detail, search, stats, update, save, enrichment, job polling, usage, export,
speaker profile, and administrative routes. Run the isolation suite in CI and against a safe staging
deployment before each release.

## 9. Ownership

| Area | Accountable owner | Required evidence |
|---|---|---|
| Authentication and token validation | Backend lead | Integration tests and rotation/revocation runbook |
| Tenant-scoped data access | Backend lead | Route inventory and negative authorization suite |
| CLI secret handling | CLI maintainer | OS keychain tests and leakage checks |
| Contact-data governance | Privacy/product owner | Data inventory, retention, deletion, and processor records |
| Logging and alerting | Operations owner | Redaction tests, alerts, and incident drill |
| Release security | Engineering owner | Signed artifacts and passing CI security checks |

Names and dates must be assigned before implementation begins. A control without an owner and
verification evidence is not complete.

## 10. Decisions needed before coding

1. Which identity provider or authentication framework will be used?
2. Is browser-based PKCE sufficient, or is Device Authorization required for headless environments?
3. What backend stack and database serve the API?
4. Can tenant filtering be centralized in the current data-access layer?
5. Which operating systems must receive native credential-store support in the first release?
6. How long will the shared-key migration window remain open?
7. What are the approved retention periods for contacts, pitches, audit events, and inactive accounts?

These decisions affect implementation details, but they do not change the core requirement: public
clients use individual scoped credentials, and the backend enforces tenant ownership on every data
access.

## 11. Definition of secure launch

SpeakerAgent is ready for a paid public CLI launch only when:

- customers no longer receive or require the shared deployment key;
- all tenant-owned resources are assigned to a verified tenant;
- every route and background job enforces tenant membership and permission;
- the authorization test matrix passes in CI and staging;
- secrets use secure storage and do not appear in routine output or logs;
- billable operations are idempotent, auditable, and cannot charge across tenants;
- contact information and pitch content are redacted by default;
- revocation, rotation, deletion, backup restore, and incident response have been exercised;
- an independent review has no unresolved critical or high findings.
