---
status: Draft
date: 2026-06-14
deciders:
  - aaronsb
  - claude
related:
  - ADR-104
  - ADR-103
  - ADR-086
  - ADR-061
  - ADR-054
  - ADR-016
  - ADR-080
---

# ADR-105: Scenario-driven TLS via an in-VM Traefik router

## Context

ADR-104 converged the **provisioning** contract across install paths but
explicitly deferred TLS: *"`install.sh` still owns concerns the others don't
(SSL/Let's Encrypt, macvlan, host shim); convergence targets provisioning, not
those."* This ADR picks up the certificate carve-out — but the investigation
turned up a better shape than the one first drafted.

### Two needs that converge on the same component

1. **HTTPS parity across install paths.** All cert logic lives in `install.sh`
   only (`SECTION 9`, ~460 lines: acme.sh/certbot, four modes, nginx config gen,
   compose overlay, renewal cron). The modern `operator.sh init` / appliance path
   cannot stand up TLS — it merely *consumes* a `docker-compose.ssl.yml` overlay
   if one exists (`common.sh:142`, `start-platform.sh:140`) and exposes
   `operator.sh recert`, which dispatches to **`operator/lib/recert.sh` — a file
   that does not exist** (`operator.sh:906`). Deploy via the appliance path and
   you get HTTP only.
2. **A consistent service endpoint.** The appliance exposes management, web, and
   API surfaces. The CLI, FUSE driver, MCP server, and any other API client need
   a *stable* endpoint regardless of internal container ports. nginx-embedded-in-
   the-web-container cannot cleanly be that single front door.

### The realization

We were about to hand-build — a DNS-provider registry, a renewal cron, nginx TLS
config — **what a reverse proxy already provides**. An in-VM router supplies all
of it: ACME (HTTP-01, TLS-ALPN-01, and DNS-01 via **lego**, which ships ~100
providers including **porkbun**), **automatic renewal**, and host/path/port
routing. Adopting one turns "build a certificate system" into "configure one and
wire our app to it" — less code, and the code we keep is glue and policy, not
ACME protocol or crypto.

### Deployment is not one-size-fits-all

The right TLS posture depends on *where* the appliance runs. There are five real
scenarios with materially different network exposure and credential trust.

## Decision

Adopt **Traefik (MIT) as the appliance's in-VM router**, drive its TLS behavior
from an explicit **deployment scenario**, and keep the four mode *names* as
Traefik `certResolver` configurations. The surviving thesis from this ADR's first
draft holds — converge cert management, four modes, offload is an `EXTERNAL_URL`
contract, self-signed default, trust-posture by exposure — only the *mechanism*
changes from acme.sh/nginx to Traefik/lego.

### 1. Deployment scenarios (the spine)

| Scenario | Network / IP | TLS terminator | Cert posture | DNS auth **on appliance** |
|----------|--------------|----------------|--------------|----------------------------|
| **dev** | containers on a dev box, no VM | none | **HTTP only** | none |
| **private** | appliance VM on trusted LAN, real name → **private IP**; may offer DHCP/route/DNS | in-VM Traefik | **manual** (cert issued off-box) / self-signed / internal DNS-01 | none (preferred); account-key tolerable *only here* |
| **internet** | single VM on a cloud, **public IP** | in-VM Traefik | **Let's Encrypt HTTP-01 / TLS-ALPN-01** (no DNS key) | none |
| **proxied** | inside an env with an LB/reverse proxy | **edge** | **offload** (`EXTERNAL_URL`, plain HTTP in VM) | none |
| **public-nat** | public but behind NAT / Cloudflare | in-VM Traefik or tunnel | **DNS-01 via challenge delegation** (`CNAME _acme-challenge → acme-dns`) or tunnel-terminated | challenge-only (never zone key) |

`operator init` selects/derives the scenario; the scenario derives the mode. The
operator chooses *where it runs*, not *which of four cert modes to reason about*.

### 2. Traefik is the in-VM router

Present in every appliance scenario (absent in **dev**, HTTP-only in **proxied**).
A single ingress routes by host/path to management / web / API, giving the stable
endpoint the CLI / FUSE / MCP need. It **replaces nginx-in-the-web-container for
ingress** (the web image goes back to just serving static assets).

### 3. Modes are Traefik `certResolver` configs

| Mode | Traefik mechanism | Default? |
|------|-------------------|----------|
| `selfsigned` | default/generated cert served by Traefik | **yes** — appliance handles itself |
| `letsencrypt` | ACME resolver: `httpChallenge` / `tlsChallenge` / `dnsChallenge` (lego) | — |
| `manual` | file provider points at an operator-supplied cert+key | — |
| `offload` | Traefik in HTTP-only mode; edge terminates | — |

### 4. lego is the DNS provider factory

The hand-built provider registry **dissolves**. A DNS-01 deployment names a lego
provider (`porkbun`, `cloudflare`, …) and passes credentials to the resolver.
porkbun is native. Adding a provider is lego's concern, not ours.

### 5. Lifecycle: Traefik owns renewal; `recert.sh` shrinks

Per-mode ownership, now mostly delegated to Traefik:

| Mode | Issue | Renew | Owner |
|------|-------|-------|-------|
| `selfsigned` | Traefik | regenerate near expiry | **appliance (Traefik)** |
| `letsencrypt` | Traefik ACME | **Traefik auto-renews** | **appliance (Traefik)** |
| `manual` | operator, off-box | operator re-supplies (Traefik file-provider hot-reloads) | operator; appliance **warns** near expiry |
| `offload` | upstream | upstream | **upstream — `recert` is a no-op** |

`operator/lib/recert.sh` becomes thin: trigger/verify for `manual`, no-op for
`offload`; Traefik handles `letsencrypt`/`selfsigned` internally. It still makes
`operator.sh recert` real, but it is no longer a renewal engine.

### 6. Offload = `EXTERNAL_URL` contract, proxy-agnostic, Traefik as reference edge

"Behind a proxy" is a first-class mode whose contract is: the operator declares
the public URL **including scheme** (`EXTERNAL_URL=https://kg.example.com`), and
the app derives scheme-sensitive outputs (OAuth `redirect_uri`, cookies, links)
from it while trusting `X-Forwarded-Proto/Host/For`. Concretely this fixes
`headless-init.sh:496` (`http://${WEB_HOSTNAME}/callback` — scheme hardcoded) and
the API-side OAuth client registration.

The contract is **proxy-agnostic** (works behind nginx / Caddy / ALB /
Cloudflare). Because the appliance speaks Traefik internally, we **recommend (not
require) Traefik as the reference edge** and ship a drop-in router+service snippet
— the offload handoff becomes Traefik-to-Traefik with matching forwarded-header
defaults. Anyone else writes their own five lines against the same contract.

### 7. Trust posture by exposure (credential blast radius)

The unacceptable risk is a network-exposed box holding a credential that can
rewrite the **whole DNS zone** (porkbun keys are account-wide — no per-zone
scoping). So: **DNS authority on the appliance is zero by default and downgradable
to zero in every public scenario.** An account-wide key is tolerable *only* in
**private** (contained, private-IP blast radius), and even there off-box issuance
(**manual** mode) is preferred. Public scenarios use HTTP-01 / TLS-ALPN (no key),
**offload** (no cert), or challenge **delegation** (a credential that can do
nothing but answer one challenge). `--manage-dns` self-FQDN, if ever built, is
opt-in and private-only; lego manages challenge TXT only, never A records.

### 8. What we still own (the glue)

Traefik is not magic. We own: **scenario → Traefik config generation** (the new
core task, replacing the cert-factory extraction); the **topology change** (add
Traefik, route web/api behind it); **`EXTERNAL_URL` + the OAuth redirect-scheme
fix** (our app's bug, not Traefik's); **policy/trust enforcement** (which resolver
per scenario, warn on account-wide key when `EXTERNAL_URL` is public, the off-box
manual path); the **offload snippet**; and the **wizard/flags** UX.

### Licensing & commercial posture

**Traefik Proxy core and lego are MIT** — permissive, irrevocable on shipped
versions, **no network-copyleft**. A managed-fleet/SaaS built on the bundled
Traefik incurs only an attribution obligation; no reconsideration needed.
**Traefik Enterprise/Hub** are optional fleet-scale products (centralized control
plane, distributed ACME, API gateway) — the legitimate, additive purchase for a
*proxied/offload edge at fleet scale*, not a forced unlock of baseline function.
This is the **anti-Neo4j**: the core capability we depend on is fully MIT and
complete. The stack's only copyleft component is **Garage (AGPL-3.0)** — a
deliberate, accepted choice; run upstream-unmodified it imposes only "offer
source." Project stance: **maximize openness; the moat is how to use the system,
not the code or hosting.** Dependency choices optimize for openness and
rug-pull-resistance, never code protection.

## Consequences

### Positive
- **Less code, not more**: the DNS-provider registry, renewal cron, and nginx TLS
  config are deleted; Traefik/lego own ACME, renewal, and routing.
- One **stable ingress** for management/web/API → consistent CLI/FUSE/MCP endpoint.
- HTTPS parity across all install paths; `operator.sh recert` stops dangling.
- Scenarios make mode-selection **defensible** instead of asking operators to
  reason about four cert modes cold.
- All load-bearing dependencies stay permissively licensed.

### Negative
- **Topology change**: Traefik replacing nginx-in-web ingress touches the
  appliance control plane (ADR-103/104) and how static assets are served. This is
  a deliberate re-plumb, **not a behavior-preserving refactor**.
- A new component (Traefik) in the appliance image.
- `install.sh`'s existing, working SSL section is **replaced**, not extracted —
  must not regress existing production installs (e.g. cube's prior install).

### Neutral
- Mode *names* and the four-mode taxonomy are unchanged; the offload `EXTERNAL_URL`
  contract and trust posture survive from the first draft intact.
- Self-managed DNS A-records (DDNS) remain out of scope — lego does challenge TXT
  only.

## Alternatives Considered

- **Hand-rolled acme.sh/nginx cert factory** (this ADR's first draft). Rejected:
  rebuilds what Traefik provides and leaves us maintaining security-sensitive ACME
  and renewal code.
- **Per-mode certs without a router.** Rejected: solves TLS but not the
  consistent-endpoint need; we'd still bolt on routing separately.
- **Require Traefik at the edge for offload.** Rejected: couples offload to one
  proxy; the contract must stay proxy-agnostic.
- **Caddy instead of Traefik** (Apache-2.0, native ACME, on-demand TLS). A genuine
  peer; rejected for now on Traefik's provider ecosystem and existing operator
  familiarity. Revisit if the open-core optics ever bite — both are permissive.

## Migration Note (non-binding sketch)

Incremental, each step shippable:

1. Add a Traefik service to the appliance topology; route web + API behind it
   (HTTP first, no TLS) — proves routing without touching certs.
2. Generate Traefik static + dynamic config from `scenario` + `EXTERNAL_URL`
   (this is the new shared module — "configure-traefik," not "configure-ssl").
3. Wire `certResolver`s: self-signed default; LE `http`/`tlsChallenge`;
   `dnsChallenge` via lego; `manual` file provider.
4. Introduce `EXTERNAL_URL`; fix the OAuth redirect scheme (`headless-init.sh:496`
   + API client registration); honor `X-Forwarded-Proto`.
5. Thin `operator/lib/recert.sh`: `manual` re-supply + `offload` no-op; Traefik
   owns LE/self-signed renewal. `operator.sh recert` works.
6. Replace `install.sh` SECTION 9 with the shared generator; verify no regression
   for existing standalone installs.
7. Ship the offload Traefik snippet + scenario docs.
8. Deploy cube as **private / manual** (cert issued off-box on north; no DNS key
   on cube) — the first real exercise, and a faithful rehearsal of **proxied**.

_This revises the acme.sh/nginx mechanism of this same ADR (still Draft,
unmerged); the decision's thesis is unchanged._
