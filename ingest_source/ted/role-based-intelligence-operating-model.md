# Role-Based Intelligence: An Operating Model for a Connected Enterprise

## Thesis
Scaling "intelligence" works best when you start with roles, not tools. Roles define the questions; questions define the signals; signals define the minimum data contracts across whatever stack you have. Tools can vary—roles don't.

**Backdrop in three beats**

1. $1
2. $1
3. $1

### **Claim**
A roles-first, graph-driven model beats framework-first or tool-first because it:

* anchors on decisions real people must make;
* tolerates heterogeneous stacks;
* creates durable data contracts that AI can reason over.

### **Implication for Atlassian & partners**
Atlassian's System of Work is directionally right but product-first; customers still need a connective tissue. That's the opening for Cprime.

### **POV**
Cprime will publish a vendor-agnostic "Signals Graph" and role-based playbooks that bind OKRs/portfolio, planning, delivery, and finance via minimal data contracts—integrating Atlassian and anything else the client runs.

## How to Read This Roles & Signals Matrix
This matrix is a **reference map of who does what and what they must know** to run a modern, remote‑first, technology‑driven enterprise on Atlassian. It's intentionally terse so you can scan it fast, but it encodes a complete operating logic:

* **Functional Areas** reflect how high‑performing orgs are structured today: Strategy/Portfolio → Product → Delivery → Operations/Reliability → GRC → GTM → Enablement. The unit of execution is the **team**; portfolios provide direction and capacity.

* **Roles** are the minimum viable set needed to scale cleanly. Titles may differ, but the **accountabilities** are consistent across companies that operate at state‑of‑the‑art.

* **Role Snapshot** captures the essence of the job—what outcomes they own—not just activities.

* **What They Do** lists the core repeatable work (decisions, reviews, and interventions) that the role performs inside an operating cadence.

* **What They Need to Know (State of Work)** names the **live signals** each role must see to make good decisions quickly. These are not vanity metrics; they are **actionable views** tied to ownership and time.

### Why this matters
Modern enterprises win on **decision latency**—how quickly the right person can act with confidence. Decision latency collapses when:

1. $1
2. $1
3. $1

### How to use it
1. $1
2. $1
3. $1
4. $1
5. $1

### Scope & extensions
* The matrix is "platform‑out": it assumes Atlassian is the backbone and integrates code, incidents, and analytics as first‑class inputs.

* It is **deliberately minimal**. Add rows only when new, durable accountabilities appear; avoid role sprawl.

* A companion guide can enumerate the exact fields, links, and automations per role, plus sample dashboards and agent patterns (Watcher, Summarizer, Router, Fixer).

Use this as a **starter kit**: get the roles right, wire the signals, and your operating model becomes teachable, measurable, and improvable.

Below is a compact, Confluence‑ready matrix you can extend. Columns are intentionally terse (≤ ~20 words) to keep the table scannable.

### Legend
* **State of work** = the live signals this role needs (status, risks, flow, outcomes) to do their job well.

| Functional Area | Role | Role Snapshot | What They Do | What They Need to Know (State of Work) |
|----------------|------|---------------|--------------|----------------------------------------|
| Executive & Strategy | CEO | Sets direction; accountable for outcomes | Aligns bets to strategy; unblocks cross‑org issues | Outcomes vs. OKRs, risk to goals, investment mix, runway, major incidents |
| Executive & Strategy | COO | Owns operating model & cadence | Drives execution discipline; removes operational bottlenecks | Plan vs. actual, cross‑team dependencies, throughput, constraint hotspots |
| Executive & Strategy | CFO | Steward of capital allocation | Funds portfolios; ensures ROI & predictability | Spend vs. plan, value delivery pace, forecast confidence, variance drivers |
| Executive & Strategy | Chief of Staff | Connects exec intent to execution | Runs rhythms; curates exec briefs & decisions | Decision backlogs, owner/ETA, exceptions, upcoming milestones |
| Strategy/Portfolio (Focus/Funds/Talent) | Head of Portfolio | Owns portfolio framing & priorities | Translates strategy to portfolios & capacity | Prioritization rationale, capacity vs. demand, portfolio health, tradeoffs |
| Strategy/Portfolio (Focus/Funds/Talent) | Portfolio Manager | Orchestrates initiatives | Tracks cross‑initiative progress & risk | Initiative status, dependency map, slippage, mitigation plans |
| Strategy/Portfolio (Focus/Funds/Talent) | PMO Lead | Standardizes governance | Ensures definitions, reviews, reporting | Compliance to standards, stage gates, exceptions |
| Product | Chief Product Officer | Owns product vision & portfolio | Allocates product bets; measures impact | Adoption/retention, outcome metrics, roadmap confidence, research pipeline |
| Product | Director/Group PM | Leads a product area | Shapes strategy; manages PMs & roadmaps | Area OKRs, discovery->delivery flow, risks, experiment readouts |
| Product | Product Manager / PO | Maximizes product value | Prioritizes backlog; connects problems to work | Customer signals, impact vs. effort, release readiness, outcome KPIs |
| Product | Product Ops | Scales PM practice | Templates, rituals, data hygiene | Roadmap currency, artifact completeness, decision latency |
| Design & Research | Head of Design/UX | Ensures product usability & craft | Sets design standards; capacity planning | Design debt, usability risks, research coverage, handoff timing |
| Design & Research | UX Designer | Delivers user experience | Designs flows; collaborates with devs | Spec readiness, status of design tasks, review queues |
| Design & Research | UX Researcher | Drives insight generation | Plans studies; synthesizes insights | Research backlog, study status, notable findings, impact on roadmap |
| Engineering (Delivery) | VP Engineering | Owns engineering execution & health | Scales teams; governs quality & velocity | DORA, reliability, hiring/capacity, bottlenecks, aging work |
| Engineering (Delivery) | Director / EM | Leads teams; manages delivery | Unblocks; coaches; manages throughput | Sprint health, WIP, carryover, PR/CI status, risk items |
| Engineering (Delivery) | Tech Lead | Technical direction for a team | Designs; reviews; ensures quality | PR size/review load, build health, hot spots, dependency risks |
| Engineering (Delivery) | Software Engineer | Builds and tests features | Implements; reviews; deploys | Assigned work, clear acceptance, CI results, code review queues |
| Platform / DevEx | Head of Platform | Owns internal platform strategy | Productizes developer platform | Platform adoption, golden path health, infra reliability, ticket load |
| Platform / DevEx | Platform Engineer | Builds platform capabilities | APIs, pipelines, templates | Backlog, SLAs, incident tickets, consumer satisfaction |
| Platform / DevEx | DevEx Lead | Improves developer experience | Measures & fixes flow friction | Cycle time, review time, flaky tests, tool latency |
| Site Reliability / Operations | Head of SRE | Reliability governance | SLOs, incident readiness, capacity | Error budgets, incident trends, toil %, change failure rate |
| Site Reliability / Operations | SRE | Operates & automates services | Runbooks; observability; incident response | Alerts, runbook gaps, deployment health, pager load |
| Security & GRC | CISO | Security posture & risk | Sets policy; prioritizes security work | Risk register, audit readiness, vuln SLA, incident scope |
| Security & GRC | AppSec Lead | Application security program | Reviews; tooling; threat modeling | Findings backlog, PR checks, dependency vulns, fix rates |
| Security & GRC | GRC Manager | Compliance operations | Evidence collection; control tests | Control status, exceptions, evidence freshness, audit dates |
| Data & Analytics | Head of Data | Data strategy & governance | Models, platforms, literacy | Data contracts, lineage, freshness SLAs, canonical metrics |
| Data & Analytics | Analytics Engineer | Models reliable datasets | Build dbt/ELT, tests, docs | Pipeline health, test failures, schema changes, consumer needs |
| Data & Analytics | Data Scientist/Analyst | Insights & decision support | Experiments; dashboards; forecasts | Experiment status, metric moves, data quality caveats |
| Customer Support / Success | Head of Support | Owns support outcomes | Staffing; SLAs; deflection | Volume, SLA attainment, CSAT, top drivers, backlog age |
| Customer Support / Success | Support Manager | Queue & team performance | Scheduling; coaching; escalations | Queue health, reopens, hotspots, knowledge gaps |
| Customer Support / Success | CSM | Customer value realization | Onboarding; adoption; renewals | Account health, risk signals, open issues, roadmap fit |
| Sales & Marketing | CRO / VP Sales | Revenue execution | Forecast; pipeline quality | Pipeline health, win/loss themes, product readiness blockers |
| Sales & Marketing | Marketing Lead | Demand & positioning | Campaigns; product marketing | Funnel metrics, message‑market feedback, launch readiness |
| Finance (FP&A) | Head of FP&A | Planning & forecasting | Budget cycles; scenario modeling | Actuals vs. plan, burn, ROI signals, hiring pipeline impact |
| People / Talent | Head of People | Talent strategy & policies | Hiring, performance, engagement | Hiring velocity, attrition risks, skills coverage, engagement |
| People / Talent | Talent Partner / Recruiter | Hiring execution | Pipelines; offers; DEI | Req status, time‑to‑hire, offer acceptance, team capacity |
| IT / Enterprise Apps | Head of IT | Productivity & SaaS hygiene | Identity, devices, MDM, apps | License posture, SSO coverage, incident tickets, change windows |
| IT / Enterprise Apps | Enterprise Apps Admin | Atlassian & SaaS config | Governance; automation; support | Schema changes, automation health, permission hygiene |
| Legal | GC / Legal Ops | Risk & contracts | Reviews; privacy; IP | Contract cycle time, high‑risk clauses, DPIAs, policy changes |
| Service Management | Head of Service Mgmt | ITSM/ESM operating model | SLAs, catalog, continual improvement | SLA heatmap, backlog, change failure, PIR actions |
| Program / Change Enablement | Change Leader | Drives adoption & behavior | Training; comms; playbooks | Adoption metrics, compliance, feedback, friction points |

### Notes
* You can map each role's "state of work" to concrete Atlassian signals (Jira/JPD issues & links, Focus Areas, Goals, JSM incidents, Compass services, Bitbucket/GitHub PRs, Deploy events, Analytics views).

* To operationalize, pair each row with a **dashboard** (3–5 tiles) and a **cadence** (daily/weekly/monthly) and define owners for data hygiene.

## The Signals Model (system-agnostic data contract)
Use this as your canonical event schema. Hydrate from Jira, Git, CI/CD, flags, incidents, etc.

**Signal (event)**

* `signal_id` (GUID)
* `signal_type` (e.g., `issue.created`, `issue.status_changed`, `pr.opened`, `pr.merged`, `deploy.completed`, `incident.started`, `incident.resolved`, `flag.released`)
* `occurred_at` (UTC ISO)
* `source` (jira, github, gitlab, bitbucket, argo, launchdarkly, opsgenie/jsm, pagerduty, compass)
* `subject`
  - `issue_key` (Jira)
  - `service_id` / `component_id` (Compass, JSM Assets)
  - `repo` + `commit_sha` (VCS)
  - `deployment_id` (CD)
  - `incident_id`
* `attributes` (bag for fields like: status_from, status_to, env=prod, severity, region, duration_ms, author, team_id, goal_id)
* `links` (array of related subject identifiers, e.g., issue ⇄ PRs ⇄ deployment ⇄ incident)

This lets you compute DORA/SPACE and alignment/ROI without being locked to any one tool. Atlassian becomes a **major hydrator** of signals, not your schema.

## Atlassian entities → the signals you need

### Jira Software (work & flow)

**Core entities**

* **Issue types**: Idea (JPD), Epic/Initiative, Story/Bug/Task, Change/Release ticket (optional)
* **Boards/Projects**: team-scoped
* **Releases**: versions (optional if you prefer CD tool as source of truth)

**Recommended fields (create once; reuse everywhere)**

*Minimum viable alignment & flow*

* `Goal` (link to Atlassian Goal)
* `Focus Area / Strategy Tag` (single select; aligns to your strategy taxonomy)
* `Team` (single select; or Team field)
* `Service / Component` (links to Compass or Component field)
* `Investment Category` (Run/Grow/Transform; or Opex/Capex if useful)
* `Requested By` (stakeholder)
* `Business Value` (score or picklist)
* `Estimate` (story points/t-shirt—pick one)
* `Risk` (picklist)
* `Blocked` (checkbox) + `Blocked Reason` (text)

*Time stamps via workflow automation (dates)*

* `Date Selected` (when moved out of Backlog)
* `Date Started` (first time status enters In Progress)
* `Date In Review` (first time status enters In Review)
* `Date Ready for Release` (optional pre-prod)
* `Date Deployed` (first production release exposure; can be hydrated from Deployments)
* `Date Done` (final)

Use **Jira Automation** to stamp these fields on the **first** entry into each status bucket (idempotent rules).

**Workflow (status categories that matter)**

* Backlog → Selected → In Progress → In Review → Ready for Release (optional) → Done (Add a "Released" status only if your team truly separates Done vs Released.)

**Which timestamps feed which metrics**

* Lead/cycle time: `Date Started` → `Date Done` (or `Date Deployed` if you want "code in prod")
* Flow efficiency: time in value-adding statuses vs. queues (requires history or data warehouse)
* WIP: count of issues in `In Progress` per team/service
* Ticket hygiene: `Blocked` flags, stale time in status, missing links (PRs, Goals)

### Jira Product Discovery (intake & prioritization)

**Entities**

* Ideas with fields: Impact, Effort, Confidence, Assumptions, Hypothesis, ROI (custom)
* Links to **Goals** and to downstream Jira delivery issues.

**Fields to standardize**

* `Linked Goal` (Goal link)
* `Target Release / Quarter` (text or picklist)
* `Owner` (person)

**Signals**

* Idea created, scored, moved to "In Progress" (becomes an Initiative/Epic), linked to delivery work.

### Atlassian Goals (Strategy Collection)

**Entities**

* Company/Strategy/Priority/Big Rock (your hierarchy)
* Goal progress roll-ups (manual or automated).

**Fields**

* OOTB link type; ensure issues and ideas link to a **single Goal field**.

**Signals**

* `goal.created`, `goal.progress_updated`, `issue.linked_to_goal` (alignment).

### Development & Deployments (Jira Dev Panel + Deployments)

When GitHub/GitLab/Bitbucket and your CI/CD connect to Jira Cloud:

**Signals Jira exposes OOTB**

* Branches, commits, pull requests (opened, merged), builds (passed/failed), **Deployments** (started/completed, env), all linked to issue keys when branch/PR titles include the key or via smart commits.

**Fields to store (optional but useful)**

* `PR URL` (first/primary)
* `PR Count` (integer)
* `Deployment ID` / `Last Prod Deploy At` (date)
* `Feature Flag ID` (if using flags as release)

**Key events**

* `pr.opened`, `pr.merged`, `build.succeeded`, `deploy.completed(env=prod)`, `flag.released`

### Incidents & Ops (JSM, Opsgenie)

**Entities**

* Major incident issues in **JSM** (or Opsgenie alerts/incidents)
* Post-incident "Problem" records (optional)

**Fields to standardize**

* `Severity` (S1–S4), `Service/Component`, `Linked Deployment` (custom link), `Root Cause` (picklist), `Mitigated At`, `Resolved At`, `Customer Impacted` (bool)

**Signals**

* `incident.started`, `incident.mitigated`, `incident.resolved`, links to deployment/change.

These power **CFR** and **MTTR**.

### Compass (service catalog) — optional but powerful

**Entities**

* Components/Services with owners, repos, environments, scorecards.

**Useful links/fields**

* `Owner Team`, `On-call`, `Repo(s)`, `Environment(s)`, `Tier`, `SLO/SLA`

**Signals**

* `component.created/updated`, scorecard check results, deploys per component.

## What's OOTB vs. where you'll need help

### OOTB Atlassian gives you

* **Jira Dev Panel & Deployments:** PR/commit/build/deploy metadata linked to issues (when integrations are configured and issue keys are referenced).
* **Automation for Jira:** stamping dates on status transitions, calculating durations, calling webhooks (no-code).
* **Atlassian Analytics & Data Lake (Enterprise):** SQL over Jira/JSM/Confluence/Assets; joins across products.
* **JPD & Goals:** intake, prioritization, and strategy linking.
* **JSM/Opsgenie:** incident timestamps and severities.
* **Compass:** catalog + ownership, a place to normalize "service" identity.

### Gaps you should expect (where services shine)

* **Consistent taxonomy**: Goals, Focus Areas, Investment Categories, Teams, Services, Environments. (Define once. Enforce.)
* **Workflow standardization**: too many bespoke flows kill comparability; define 1–2 canonical flows per work type.
* **Golden timestamps**: Atlassian records *events*, but you must **decide and enforce** which event = "start," "review," "deployed," etc., and stamp those to fields consistently.
* **Backfilling & data quality**: populate missing Goal links, Team, Service/Component, and retro-stamp dates for in-flight items.
* **Feature-flag exposure**: if you dark deploy, you need a rule to count **exposure** as the deployment for metrics.
* **DORA truth source**: choose CD/Flags/Deployments as system-of-record and reconcile duplicates (multi-region, retries).
* **Join keys**: make sure every repo/PR/deploy/incident can be deterministically tied to a Jira issue and/or a Service.
* **Benchmarks & outliers**: Analytics modeling to avoid Simpson's paradox; p50/p85/p95 reporting.
* **Portfolio rollups**: cross-team rollups and allocation/ROI slices (by Goal, Focus Area, Team, Service, Value Stream).
* **Guardrails & automation**: policy-as-code for PRs (min reviewers, size thresholds, CI green), stale-ticket nudges, WIP limits.
* **Training & change mgmt**: team-level agreements to prevent the "surveillance" anti-pattern.

## Concrete "field & workflow" starter pack

### Jira custom fields (create globally; use context by project)

**Alignment & ownership**

* `Goal` (link field to Atlassian Goal)
* `Focus Area` (single select)
* `Investment Category` (single select)
* `Team` (Team picker or single select)
* `Service / Component` (Component or Compass link)
* `Customer Impacted` (checkbox)

**Flow timestamps (date fields; set once via automation)**

* `Date Selected`
* `Date Started`
* `Date In Review`
* `Date Ready for Release` (optional)
* `Date Deployed` (hydrate from Deployments or flags)
* `Date Done`

**Quality & risk**

* `Blocked` (checkbox), `Blocked Reason` (text)
* `Severity` (for bug/incident types)
* `Defect Origin` (picklist; optional)

**Traceability helpers (optional)**

* `Primary PR URL`
* `Last Prod Deploy At` (date/time)

Keep it lean. Too many fields = poor hygiene. The above covers 90% of intelligence use-cases.

### Workflow (with automation rules)

Statuses:

* **Backlog → Selected → In Progress → In Review → Done** (+ optional **Ready for Release**, **Released** if truly needed)

Automations (idempotent):

* On status **changes to Selected** → set `Date Selected` if empty
* On **first move to In Progress** → set `Date Started` if empty
* On **first move to In Review** → set `Date In Review` if empty
* On **Deployments: env=prod completed** for linked issue → set `Date Deployed` if empty
* On transition to **Done** → set `Date Done` if empty
* On **issue created** → require `Team`, `Service/Component` via validator; nudge to add `Goal` if missing

## How to hydrate the model (end-to-end)

**Sources**

* Jira Cloud (REST/GraphQL), Webhooks, Automation outgoing webhooks
* GitHub/GitLab/Bitbucket webhooks (PR, commit, tag, merge)
* CI/CD (Actions, GitLab CI, Jenkins), CD (Argo, Spinnaker, Octopus)
* Feature flags (LaunchDarkly, Split)
* JSM/Opsgenie/PagerDuty incidents
* Compass (service catalog)
* Confluence (optional knowledge signals)

**Pipelines**

* Use a small event collector (serverless or container) to accept webhooks → validate → map into your **Signal** schema → push to event bus / warehouse (e.g., Kinesis, Pub/Sub, Kafka → Snowflake/BigQuery/Redshift).
* Nightly backfills from Atlassian **Data Lake** (if on Enterprise) or via REST pagination for history.
* Idempotency keys = the upstream event ID to avoid dupes.

**Identity links (critical)**

* Enforce **issue key in branch/PR title** (or use Dev Panel linkers).
* Maintain a `service ⇄ repo(s)` registry (Compass or a CSV you later move to Assets).
* Write a small resolver to attach `deployment_id → commit_shas → PRs → issue_keys` and `incident_id → deployment_id`.

## What Cprime should sell (service partner POV)

**A. Signals & Data Contract**

* Define the **Signals schema** and a minimal **data contract** per source (what fields are required; how we derive goal alignment, service, team).
* Deliver a reference implementation (webhook collector + mapping library).

**B. Atlassian Governance Kit**

* Field taxonomy (above), global contexts, naming, screens, permissions.
* Canonical workflows per work type + idempotent date-stamping automations.
* Quality gates: validators for Team/Service/Goal, WIP limits, PR policy templates.

**C. Service Catalog & Ownership**

* Stand up Compass (or JSM Assets) to normalize service identity and map repos/envs/teams/SLIs.

**D. DORA/SPACE & Alignment Dashboards**

* Portfolio and team views (p50/p85/p95); allocation vs. intent (Goal/Focus Area).
* "Hygiene heatmap" (missing fields/links, stale statuses, untracked deploys) to drive coaching.

**E. GenAI Readiness & Micro-Bots**

* Conversational Q&A over the warehouse.
* Bots: merge-gatekeeper, stale-ticket nudger, "missing Goal link" fixer, incident-to-deploy linker.

**F. Change Management**

* Working agreements, playbooks, and enablement focused on **team-level** metrics (not individual surveillance).

---

*Source: [Confluence Page](https://cprimeglobalsolutions.atlassian.net/wiki/spaces/~712020314f78ab81f146bfbcc6b2e8b87afaa6/pages/502267905/Role-Based+Intelligence+An+Operating+Model+for+a+Connected+Enterprise)*

*Last Modified: 2025-10-06*
