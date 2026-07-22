# SpeakerAgent CLI Revenue Plan

Status: Starter proposal
Date: 2026-07-21
Currency: USD, before applicable tax

## Recommendation in one page

Launch SpeakerAgent CLI as a subscription with included monthly usage, then charge for additional
cost-bearing actions. The first paid offer should be **Starter at $29/month or $290/year**.

Do not charge for reading already-generated results, saving a lead, changing pipeline status, or
viewing account usage. Charge credits when SpeakerAgent creates new value or incurs a variable cost:

- discovering and scoring a new podcast match;
- finding and verifying a new contact;
- generating or regenerating a personalized pitch;
- exporting data at meaningful volume;
- calling the API above the included allowance.

The initial offer:

| Plan | Monthly price | Included usage | Best for |
|---|---:|---|---|
| Trial | $0 for 7 days | 10 matches, 3 enriched pitches, no bulk export | Product evaluation |
| Starter | **$29** | 1 speaker, 100 active matches, 20 enrichment credits/month, CLI/API access | Independent speakers |
| Pro | $79 | 3 speaker personas, 500 active matches, 75 enrichment credits/month, JSONL/CSV export, analytics | Consultants and power users |
| Agency | $249 | 10 speakers, 5 seats, 300 enrichment credits/month, roles, audit log, consolidated usage | PR and booking teams |
| Enterprise | From $750 | Contracted volume, SSO, support SLA, custom retention and limits | Larger organizations |

Annual plans receive two months free. Unused monthly credits do not roll over at launch; separately
purchased credit packs expire after 12 months, subject to local law. Every screen and CLI response
must show remaining usage and the credit cost before a paid action.

## 1. What one credit buys

Use one customer-facing unit: an **enrichment credit**.

| Action | Credit charge |
|---|---:|
| Read, list, filter, save, or update status | 0 |
| Reveal an already-paid contact or pitch | 0 |
| Generate a pitch using data already held | 0.25 |
| Find and verify one new host contact | 0.75 |
| Standard `refresh` containing contact lookup plus pitch | 1 |
| Refresh that produces no new usable contact or pitch | 0 |

Internally, meter every provider call and model token separately. Customers should see a simple,
stable unit even if vendors or models change. A refresh is idempotent: retries and identical results
within 24 hours cannot charge twice.

Starter overage options:

- 10 credits: $9;
- 50 credits: $35;
- 200 credits: $100;
- auto top-up is off by default and requires an explicit monthly spending cap.

This makes a normal Starter refresh worth $0.70-$0.90 above the allowance while giving larger buyers
volume discounts. Do not offer unlimited enrichment; it creates abuse and unpredictable margins.

## 2. Why start at $29

As of July 2026, nearby self-service products span roughly $15/month for marketplace-style matching
to $49-$199/month for database, outreach, and agency workflows. A podcast-data API is offered at
$99/month with metered overage. SpeakerAgent currently provides matching, enrichment, pitch drafting,
and pipeline updates, but does not yet provide a complete email sending and follow-up workspace.

At $29, Starter is:

- low enough for a solo speaker to try without an agency budget;
- high enough to validate willingness to pay and support acquisition costs;
- below fuller outreach products while the CLI has fewer workflow features;
- able to move to $39-$49 after outcome tracking, email integration, and recurring recommendations
  are proven.

Do not launch permanently below $19. Low pricing attracts support-heavy and enrichment-heavy usage,
makes paid acquisition difficult, and weakens the value signal. If conversion is the concern, use a
limited trial or a first-month promotion instead of a permanently cheap plan.

## 3. Unit economics guardrail

Before accepting payment, measure the fully loaded variable cost of each refresh:

```text
refresh COGS = contact-provider charge
             + verification charge
             + model/API charge
             + variable hosting and queue cost
             + payment fee allocated per customer
             + expected refund/failure cost
```

Starter is viable only if its average monthly variable COGS is **no more than $8.70**, preserving a
70% contribution margin on $29 revenue. The operating target should be 80% gross margin, or no more
than $5.80 average variable COGS.

Example planning case, not a claim about current costs:

| Item | Assumption |
|---|---:|
| Average Starter credits consumed | 12 of 20 |
| Average variable cost per consumed credit | $0.20 |
| Enrichment COGS | $2.40 |
| Allocated payment and variable infrastructure | $1.75 |
| Total variable COGS | $4.15 |
| Contribution before fixed payroll/marketing | $24.85 (85.7%) |

If measured cost exceeds $0.35 per credit, reduce included credits or renegotiate providers before
scaling. Never quietly lower delivered data quality to protect margin.

## 4. Revenue potential

These are planning scenarios, not forecasts. They exclude annual prepayment, overages, enterprise
contracts, refunds, taxes, and churn.

| Paying customers | Example mix | MRR | ARR run rate |
|---:|---|---:|---:|
| 25 | 20 Starter, 5 Pro | $975 | $11,700 |
| 100 | 60 Starter, 30 Pro, 10 Agency | $6,600 | $79,200 |
| 250 | 150 Starter, 75 Pro, 25 Agency | $16,500 | $198,000 |
| 1,000 | 600 Starter, 300 Pro, 100 Agency | $66,000 | $792,000 |

At the example 100-customer mix, a blended 80% gross margin leaves approximately **$5,280/month**
after variable costs but before salaries, product development, support, sales, and marketing.

The practical starter objective is **25 paying customers and about $1,000 MRR**, followed by 100
customers and $6,000-$7,000 MRR. Avoid treating the larger scenarios as budgets until activation,
retention, and acquisition data support them.

## 5. Packaging rules

### Trial

- No credit card for the first experiment; require verified email and basic abuse controls.
- Provide enough usage to complete one real workflow: discover, enrich, draft, and update status.
- Watermark exports and prohibit bulk access.
- A person, account, domain, and payment instrument may not repeatedly claim trials.

### Starter

- The primary conversion promise is: **find and prepare 20 high-fit podcast opportunities each
  month for less than the cost of one hour of manual research**.
- Include CLI and API access; do not charge developers merely for choosing the CLI.
- Keep one speaker/persona and one seat to make the Pro upgrade understandable.

### Pro

- Sell workflow speed: more personas, scheduled recommendations, exports, outcome analytics, and
  integrations.
- Add email/CRM integration only with explicit user authorization; replies and status updates remain
  unmetered.
- Raise Pro to $99 only when recurring recommendations and outreach analytics reliably save time.

### Agency

- Sell governance and capacity, not just credits: seats, roles, client separation, approvals, audit
  logs, spending controls, and consolidated reporting.
- Charge $25/month for each speaker beyond 10 and $15/month for each seat beyond 5, with fair-use API
  limits. Include credits separately so client count and enrichment cost are not conflated.

## 6. Billing and entitlement design

The server—not the CLI—owns billing decisions and usage balances.

Required resources:

- `subscription`: tenant, plan, status, billing period, renewal, cancellation;
- `entitlement`: feature, limit, current value, effective dates;
- `usage_event`: tenant, actor, action, units, idempotency key, source request, timestamp;
- `credit_ledger`: grant/purchase, debit, reversal, expiry, balance after event;
- `invoice_reference`: payment-provider IDs without card data;
- `spend_limit`: monthly cap, warning thresholds, auto-top-up choice.

Required behavior:

1. `refresh --quote <id>` returns expected credits and whether the result may be chargeable.
2. `refresh <id>` atomically reserves a credit before work begins.
3. A successful usable result captures the reservation.
4. A failed job or no-result outcome reverses it automatically.
5. Retrying with the same idempotency key returns the original outcome and charge.
6. `speakeragent usage` shows balance, included allocation, purchased credits, expiry, and recent
   ledger entries.
7. Webhooks are verified, replay-protected, and processed idempotently. A failed payment enters a
   grace period; it never deletes customer data immediately.
8. Cancellation stops renewal but preserves paid access until the period ends. Export and deletion
   remain available afterward according to policy.

## 7. 90-day launch plan

### Days 1-14: validate willingness to pay

- Interview 15 independent speakers and 10 PR/agency operators.
- Demo the existing workflow and ask each prospect to choose between $19, $29, $39, and “would not
  buy”; do not ask only whether they like it.
- Recruit 10 design partners. Charge at least 5 of them a refundable $29 founding-month payment to
  distinguish interest from purchase intent.
- Instrument activation, refresh completion, useful-contact rate, pitch edit/copy, status movement,
  and return usage. Obtain the required consent; never put pitch bodies or contact details in product
  analytics.
- Measure actual cost per enrichment and support minutes per active customer.

**Gate:** at least 5 paid design partners, at least 60% complete one enrichment, and no unresolved
tenant-isolation or billing-integrity issue.

### Days 15-45: build the paid Starter

- Implement scoped authentication and tenant authorization before billing.
- Add the usage ledger, credit reservation/reversal, idempotency, plan entitlements, and spend caps.
- Add `auth`, `usage`, `refresh --quote`, clear upgrade errors, and safe redacted output to the CLI.
- Integrate hosted checkout and billing management; avoid handling card data directly.
- Publish price, credit definition, refund/failure behavior, privacy terms, and cancellation flow.
- Add weekly cost and margin reporting by plan and provider.

**Gate:** all billable operations reconcile to the ledger; duplicate requests cannot duplicate
charges; 100% of backend routes pass tenant-isolation tests.

### Days 46-60: small paid launch

- Offer $29 Starter and $79 Pro to a capped cohort of 50 accounts.
- Give founding customers the $29 price for 12 months, not for life.
- Use product-led acquisition: CLI quickstart, three real workflow examples, and a usage calculator.
- Add referral credit only after the referred account makes its first payment; cap fraud exposure.
- Hold weekly reviews of activation, failures, refunds, cost, and user-reported result quality.

**Gate:** 15% or better trial-to-paid conversion, 60% or better month-one retained usage, less than
5% refund rate, and at least 75% gross margin.

### Days 61-90: refine and expand

- Test $29 versus $39 only on new traffic after at least 100 qualified trial starts.
- Launch Agency to 5-10 design partners only after delegation and audit controls are ready.
- Improve the highest-loss activation step before buying significant traffic.
- Add overage packs once usage distribution and provider costs are understood.
- Decide whether to keep, raise, or repackage Starter using conversion, retention, margin, and
  customer outcome data together.

## 8. Metrics and decision rules

Weekly dashboard:

- visitor-to-trial and trial-to-activation;
- activation-to-paid conversion;
- percentage of paid accounts using the product in weeks 2, 4, and 8;
- logo and revenue churn;
- average revenue per account and expansion revenue;
- credits granted, consumed, reversed, and expired;
- variable COGS per consumed credit and gross margin by plan;
- usable-contact rate and refresh failure rate;
- number of pitches copied/sent and user-confirmed replies/bookings;
- support minutes, refund rate, and billing disputes.

Decision rules after the first 100 qualified trials:

- If activation is below 50%, fix onboarding before lowering price.
- If activation is healthy but paid conversion is below 10%, test packaging and the $19 first-month
  offer; do not permanently cut list price yet.
- If paid conversion exceeds 25% and month-two retention exceeds 70%, test Starter at $39.
- If gross margin is below 70%, adjust included credits/provider costs before acquiring more users.
- If users consume fewer than 25% of credits but retain, sell the outcome and simplify usage messaging.
- If usage is high but confirmed outcomes are low, improve match/contact quality before increasing
  limits.

## 9. Monetizing aggregate usage data later

Do not include external data monetization in the first 90 days. It adds legal, trust, and engineering
work before the core subscription is validated.

After enough customers and consented data exist, sell **aggregate benchmark features**, not raw data:

- category-level demand and reply benchmarks;
- time-to-response and booking-rate ranges;
- podcast activity and topic-momentum indexes;
- private “your performance versus similar campaigns” reports;
- an aggregate insights API for agencies or research customers.

Possible later pricing is $49/month as a Pro add-on, $199/month for an agency benchmark dashboard,
or from $500/month for a contracted aggregate insights API. Release only cohorts meeting the privacy
thresholds in `PRODUCT_SECURITY_DATA_SPEC.md`; exclude identifiers, pitches, contact lists, and
tenant-level histories. Treat these prices as discovery hypotheses until buyers sign letters of intent
or pay for a pilot.

## 10. Immediate next actions

1. Approve **$29 Starter / $79 Pro / $249 Agency** as the pricing hypothesis.
2. Calculate the true cost of 100 recent refreshes and set the credit cost ceiling.
3. Interview 25 prospects and collect at least five real Starter payments.
4. Build scoped authentication and tenant isolation before distributing paid credentials.
5. Implement an auditable credit ledger before enabling overages.
6. Launch to 50 accounts, measure for two billing cycles, then decide whether Starter stays at $29 or
   moves to $39.

## Market references

- MatchMaker.fm advertises an individual plan at $15/month and an agency plan at $99/month as of
  July 2026: <https://www.matchmaker.fm/find-guests/podcasts> and
  <https://www.matchmaker.fm/for-agencies>.
- Podseeker advertises workflow plans at $49, $99, and $199/month, plus a $99/month API with 2,000
  credits and $0.05/credit overage as of July 2026: <https://www.podseeker.co/pricing>.
- Apollo documents the broader market convention of charging credits for verified contact data and
  AI research: <https://knowledge.apollo.io/hc/en-us/articles/9527776320781-What-Are-Credits>.

Competitor claims and prices can change and do not prove SpeakerAgent conversion or customer
outcomes. They define a market corridor; SpeakerAgent's own paid experiments should set final prices.
