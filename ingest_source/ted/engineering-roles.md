# Engineering Roles

# Overview
This document zooms into Engineering. It gives you a consistent way to describe each role, prove you understand their reality, and wire their needs to concrete Atlassian objects and signals.

## How to use this guide
1. $1
2. $1
3. $1
4. $1

## Common structure for each role
* **Snapshot:** mandate in 1–2 sentences
* **Major needs:** what they must accomplish repeatedly
* **Evidence we understand the job:** day‑in‑the‑life, top questions, failure modes
* **Key signals:** the minimum set they rely on
* **Atlassian mapping:** issues, links, fields, events, and where the signal lives
* **Default dashboard:** 3–5 tiles (single screen)
* **Automations / Rovo agents:** Watcher, Summarizer, Router, Fixer patterns
* **Cadence:** daily/weekly/monthly rituals fed by the dashboard

✳️ Tip: Keep tile names as questions (e.g., "Where is work stuck?") and show p50/p90 + the long tail list for action.

## Role Cards

### 1) VP of Engineering
**Snapshot**: Scales teams and systems to deliver outcomes predictably and safely.

**Major needs**

* Allocate capacity to strategy; de‑risk execution
* Govern quality, reliability, and flow across org
* Hire/retain; grow leaders; reduce decision latency

**Evidence we understand the job**

* *Top questions*: Are we on track for our bets? Where are we bottlenecked? Is quality improving? Do we have enough capacity?
* *Failure modes*: Hero culture; hidden dependencies; carryover rises; incident regressions; hiring lags demand.

**Key signals**

* **Outcome vs. plan** (initiative burn/forecast)
* **DORA** (LT, CFR, Deployment Frequency, MTTR)
* **Flow** (cycle time p90, WIP, aging work)
* **Investment mix** (New/Enhance/KTLO/Risk)
* **Reliability posture** (SLOs, error budget, sev1s)

**Atlassian mapping**

* **Initiatives/Programs** in Jira linked to **Goals/Focus Areas** (Focus/Goals).
* **Issues** (Story/Bug/Task) carrying **Allocation** and **Initiative** fields.
* **SCM/CI/CD** events → Analytics: PR merged, deployment completed.
* **JSM incidents** with sev/MTTA/MTTR fields; **Compass** for service ownership & SLOs.

**Default dashboard (tiles)**

1. $1
2. $1
3. $1
4. $1
5. $1

**Automations / Rovo**

* **Watcher**: Cycle‑time p90 breached in any team → notify Dir/EM with outlier list.
* **Summarizer**: Weekly exec brief: outcomes, flow, reliability, top risks.
* **Router**: Sev1 opened on Tier‑0 service → page owner, create war‑room, link PIR template.
* **Fixer**: Backfill missing Initiative/Allocation on issues via heuristic + confirmation.

**Cadence**: Weekly eng staff; monthly portfolio; quarterly capacity review.

### 2) Director / Engineering Manager (EM)
**Snapshot**: Delivers outcomes through teams; removes bottlenecks; coaches people.

**Major needs**

* Keep teams predictable; manage dependencies
* Maintain quality bar; balance throughput vs. WIP
* Develop talent; protect focus

**Evidence**

* *Top questions*: What's blocked? Who's overloaded? Are reviews stalling? What will slip next sprint?
* *Failure modes*: Too much WIP; review queue pile‑ups; hidden unplanned work; stale bugs.

**Key signals**

* Sprint health (commit vs. done; carryover)
* WIP & *age in state*; blocked time
* PR review time & unreviewed PRs aging
* Defect escape & flaky tests

**Atlassian mapping**

* Jira boards with **Required fields** (Owner, Team, Initiative, Acceptance Criteria).
* PR/CI events mapped to issues; test runs in build.
* Dependency links across projects; due dates.

**Default dashboard**

1. $1
2. $1
3. $1
4. $1

**Automations / Rovo**

* Watcher: PR > X LOC or > Y hrs unreviewed → nudge + suggest reviewers.
* Summarizer: Standup brief from Jira/PRs; Retro deltas.
* Router: New dependency blocker → alert owning team lead.

**Cadence**: Daily triage; weekly team review; sprint/retro.

### 3) Tech Lead
**Snapshot**: Sets technical direction; ensures code quality and delivery clarity.

**Major needs**

* Keep design coherent; reduce review latency
* De‑risk integrations; guard boundaries/contracts

**Evidence**

* *Top questions*: Are we building the right shape? Is the PR queue sane? Where are hotspots?
* *Failure modes*: Big‑bang PRs; unclear acceptance; hidden coupling; flaky tests ignored.

**Key signals**

* PR size & review time; rework rate
* Hotspot files (churn×complexity proxy)
* Test health; build stability
* Explicit acceptance criteria coverage

**Atlassian mapping**

* PR metrics from SCM; link to Jira issue.
* "Acceptance Criteria" custom field; status checks.
* CI test summaries; flaky test tag.

**Default dashboard**

1. $1
2. $1
3. $1

**Automations / Rovo**

* Fixer: Propose PR split for >N LOC; generate test checklist.
* Watcher: Build failures flapping → open tech‑debt task with context.

**Cadence**: Daily PR review pass; weekly design sync.

### 4) Software Engineer (IC)
**Snapshot**: Delivers well‑tested increments, collaborates via reviews, ships frequently.

**Major needs**

* Clarity of scope & acceptance
* Fast feedback on builds/reviews

**Evidence**

* *Top questions*: What's my next most important task? Why is my PR stuck? Are tests flaky?
* *Failure modes*: Waiting on reviews; unclear acceptance; context switching.

**Key signals**

* Assigned work with acceptance criteria ready
* Review queue position & ETA
* Build status & flake detectors

**Atlassian mapping**

* Jira backlog with DoR validators; reviewer assignment via CODEOWNERS.
* CI status checks; PR comments; feature flags link.

**Default dashboard**

1. $1
2. $1
3. $1

**Automations / Rovo**

* Summarizer: PR context (diff + linked issue spec) for reviewers.
* Fixer: Generate unit test scaffolds from ACs.

**Cadence**: Personal daily plan; code review SLAs.

### 5) Platform Engineer
**Snapshot**: Productizes the internal platform—pipelines, templates, golden paths.

**Major needs**

* Reliability of CI/CD and developer onboarding
* Template adoption and consumer satisfaction

**Evidence**

* *Top questions*: Are pipelines fast & reliable? Which templates are underused and why?
* *Failure modes*: DIY drift; long build times; unclear docs; ticket pile‑ups.

**Key signals**

* Pipeline success rate & duration
* Template adoption & drift detections
* Ticket backlog & SLAs (JSM)

**Atlassian mapping**

* Build metrics; repo checkers; policy as code results.
* JSM platform queue; Knowledge base usage.

**Default dashboard**

1. $1
2. $1
3. $1

**Automations / Rovo**

* Watcher: New repo without pipeline template → open PR to add.
* Fixer: Auto‑create CI skeleton on repo creation.

**Cadence**: Weekly platform office hours; monthly roadmap review.

### 6) DevEx Lead
**Snapshot**: Improves developer productivity by removing friction and measuring flow.

**Major needs**

* Identify & fix systemic delays (reviews, builds, environment)
* Make work visible; reduce context switching

**Evidence**

* *Top questions*: Where is time lost? Which teams need help? What's the ROI of changes?
* *Failure modes*: Vanity metrics; improvements without adoption; hidden queueing delays.

**Key signals**

* End‑to‑end cycle‑time stages; PR review time; build time; local env setup time
* Context switching (issues/person), after‑hours work (anti‑signal)

**Atlassian mapping**

* SCM/CI events; Jira transitions; calendar signals (optional); survey pulses

**Default dashboard**

1. $1
2. $1
3. $1

**Automations / Rovo**

* Summarizer: Weekly flow report with suggested experiments.
* Router: Offer pairing to teams breaching thresholds.

**Cadence**: Bi‑weekly experiment review; monthly exec readout.

### 7) Head of SRE / SRE
**Snapshot**: Protects reliability with SLOs, automation, and sharp incident response.

**Major needs**

* Maintain error budgets; reduce MTTR; control toil
* Enforce safe change; drive PIR learning

**Evidence**

* *Top questions*: Which services are burning budget? Where does MTTR spike (detect/diagnose/repair)?
* *Failure modes*: Alert fatigue; manual runbooks; no change gating.

**Key signals**

* SLO attainment & error‑budget burn
* Incident count/MTTR by stage; change failure rate
* Toil % and runbook automation coverage

**Atlassian mapping**

* Compass service catalog + SLOs; JSM incidents & changes; CI deploy events; Statuspage incidents

**Default dashboard**

1. $1
2. $1
3. $1

**Automations / Rovo**

* Watcher: Budget burn rate breach → auto‑throttle risky deploys.
* Fixer: Generate PIR draft from JSM timeline and logs.

**Cadence**: Weekly SRE review; monthly reliability council.

### 8) Quality Lead / Test Engineer
**Snapshot**: Ensures product quality through test strategy, tooling, and feedback loops.

**Major needs**

* Shift‑left quality; reduce escapes; stabilize tests

**Evidence**

* *Top questions*: Where do defects originate? Are tests giving fast, reliable feedback?
* *Failure modes*: Flaky suites; slow feedback; late discovery.

**Key signals**

* Defect escape rate; test flake rate; time‑to‑test feedback; coverage deltas (risk‑based)

**Atlassian mapping**

* Jira bugs linked to stories; CI test results; Zephyr/Xray (if used); feature flags for gradual rollout

**Default dashboard**

1. $1
2. $1
3. $1

**Automations / Rovo**

* Watcher: Flaky test detected → quarantine + ticket with failure history.
* Fixer: Suggest missing tests from ACs and recent bugs.

**Cadence**: Sprint planning input; weekly quality clinic.

## SPACE & Team Pain Radar (privacy‑safe, team‑first)
**SPACE** gives a balanced view across Satisfaction/Well‑being, Performance, Activity, Collaboration, and Efficiency/Flow. We use **team‑level** signals only, paired with flow data already in Atlassian. No individual scorecards.

### Team‑level SPACE signals (pragmatic set)

| SPACE dim. | Practical signal | Atlassian wiring | Guardrail |
|------------|------------------|------------------|-----------|
| Satisfaction & Well‑being | Quarterly 5‑item pulse (S/WB index) + eNPS | Confluence/JSM form → Atlassian Analytics (aggregate by Team) | Anonymous; suppress n<5 |

## Cross-role data contracts (Engineering)
* **Deployed marker of record**: DeploymentCompleted(event) with service, env, commit, issue keys.
* **Ownership**: Every service in Compass has team owner; every issue has Team & Initiative.
* **Required fields**: Owner, Team, Focus Area/Initiative, Acceptance Criteria for Stories; Severity & Root Cause for Incidents.
* **Linking**: Idea ↔ Initiative ↔ Story/Bug; Change ↔ Incident ↔ PIR page.

## Starter dashboard pack (ship first)
1. $1

## Appendix: Field & entity mapping (starter)
* **Jira (Software)**: Project, Issue types (Initiative, Epic, Story, Bug, Task), Custom fields (Initiative Link, Allocation, Acceptance Criteria, Risk, Team).
* **Jira Product Discovery**: Idea template (Problem, Outcome, Impact/Effort, Decision), auto‑create Initiative.
* **Jira Service Management**: Incident, Change, PIR template; sev, MTTA/MTTR stages, affected service.
* **SCM/CI/CD**: PR events, build status, deploy events tagged with service/env/issue.
* **Compass**: Service catalog, team ownership, SLOs/scorecards, runbooks.
* **Atlassian Analytics**: Metric views for DORA/flow/investment; join across Jira/JSM/Compass

---

*Source: [Confluence Page](https://cprimeglobalsolutions.atlassian.net/wiki/spaces/~712020314f78ab81f146bfbcc6b2e8b87afaa6/pages/502398980/Engineering+Roles)*

*Last Modified: 2025-09-26*
