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
  - ADR-801
---

# ADR-105: TLS/certificate convergence — unified cert factory and reverse-proxy offload contract

## Context

ADR-104 converged the **provisioning** contract across the three install paths
(`operator.sh init`, `install.sh`, appliance first-boot) but explicitly carved
out TLS:

> `install.sh` still owns concerns the others don't (SSL/Let's Encrypt, macvlan,
> host shim); convergence targets provisioning, not those.

This ADR picks up that carve-out for the **certificate subsystem**. The carve-out
was the right call for ADR-104's scope, but the drift it names is now biting the
appliance and host-install (cube) work directly.

### The drift

All certificate logic lives in **`install.sh` only** — `SECTION 9: SSL SETUP`
(~`install.sh:1875-2336`): `setup_ssl`, `setup_selfsigned_ssl`,
`setup_letsencrypt_dns`, `setup_letsencrypt_http`, `setup_manual_ssl`,
`setup_cert_renewal`, `generate_nginx_ssl_config`, `generate_ssl_compose_overlay`,
`check_existing_acme_cert`, `show_cert_info`. It already models the right
four-mode taxonomy:

| Mode | Who terminates TLS | Default? |
|------|--------------------|----------|
| `selfsigned` | the appliance (bundled self-signed cert) | — |
| `letsencrypt` | the appliance (acme.sh DNS-01 / certbot HTTP-01) | — |
| `manual` | the appliance (operator supplies cert+key) | — |
| `offload` | **external** reverse proxy (Traefik/nginx/Caddy/HAProxy) | — |

The **`operator.sh init`** path (the one the appliance and source-present hosts
use) cannot set up any of this. It only *consumes* a `docker-compose.ssl.yml`
overlay if one already exists (`operator/lib/common.sh:142`,
`operator/lib/start-platform.sh:140`, `operator.sh:100`), and exposes
`operator.sh recert` — which dispatches to **`operator/lib/recert.sh`, a file
that does not exist in the repo** (`operator.sh:906`). The operator path's one
advertised cert capability is a dangling reference.

Net effect: **to get HTTPS today you must use `install.sh`.** Deploy via the
modern appliance/operator path and you get HTTP-only. That is the same
two-installers-one-capability drift ADR-104 fought, scoped to certs.

### Two latent defects the convergence must fix

1. **DNS provider handling is a hardcoded `case`.** `setup_letsencrypt_dns`
   switches on `$SSL_DNS_PROVIDER` (`dns_porkbun`/`dns_cloudflare`/
   `dns_digitalocean`/`dns_gandi`/generic) to export the right env vars
   (`install.sh:~1970`). Every new provider edits that switch. There is no
   registry — adding a provider is a code change in the middle of a 460-line SSL
   block.

2. **The OAuth redirect scheme is hardcoded to `http://`.**
   `operator/lib/headless-init.sh:496` builds
   `REDIRECT_URI="http://${WEB_HOSTNAME}/callback"`. `WEB_HOSTNAME` conflates
   *what host* with *what scheme*. The instant anything terminates TLS in front
   of the app (offload mode, or the app's own 443), the registered redirect URI
   is `http://` while the browser is on `https://` → OAuth breaks. This is the
   load-bearing reason "offload" must be a real mode, not just "disable TLS."

### The proven convergence mechanism

This is not novel work — it is the same move ADR-104 endorses and that AI/embedding
config already shipped (ADR-801, commits `cdc7ce493`/`837c6cd5e`): `install.sh`
deliberately does **not** ship the full `operator/lib`; it downloads the specific
shared helper and sources it (`install.sh:1775-1785` for `configure-ai.sh`,
sourced at `:2534`). SSL is the last capability still living only in `install.sh`.

## Decision

Extract certificate management into a **shared `operator/lib/configure-ssl.sh`**,
sourced by every install path, exposing the four-mode taxonomy, a DNS-01
**provider factory**, a real renewal entry point, and a first-class **offload
contract**.

### 1. Shared cert library

`operator/lib/configure-ssl.sh` owns mode dispatch and artifact generation
(`certs/`, `nginx.ssl.conf`, `docker-compose.ssl.yml`). Both consumers source it:

- `install.sh` — downloads it alongside `configure-ai.sh` and sources it
  (existing pattern); the `SECTION 9` functions become thin wrappers or are
  deleted in favor of the shared entry point. **Behavior-preserving** for
  existing `install.sh` users.
- `operator.sh init` — `headless-init.sh` / `guided-init.sh` gain `--ssl MODE`
  (+ `--ssl-email`, `--ssl-cert`, `--ssl-key`, `--ssl-dns-provider`,
  `--ssl-dns-key`, `--ssl-dns-secret`) and call the same library.

**Default mode = `selfsigned`** so the appliance "handles itself": it boots with
working HTTPS and no external dependency, with a documented upgrade path to a
real cert. An appliance that requires an external proxy to be reachable is not an
appliance.

### 2. DNS-01 provider factory

Replace the hardcoded `case` with a **descriptor registry**. A provider is a row:

```
provider id     acme.sh dnsapi    required env (our var → acme var)
porkbun         dns_porkbun       SSL_DNS_KEY→PORKBUN_API_KEY, SSL_DNS_SECRET→PORKBUN_SECRET_API_KEY
cloudflare      dns_cloudflare    SSL_DNS_KEY→CF_Token
digitalocean    dns_digitalocean  SSL_DNS_KEY→DO_API_KEY
```

**porkbun is the reference provider** (the maintainer's DNS). The factory maps a
provider id → its acme.sh dnsapi name + the env-var translation it needs; issuance
is otherwise provider-agnostic (acme.sh does the protocol work). Adding a provider
= adding a descriptor row, never touching issuance logic. Unknown ids fall through
to a generic path that passes env through untranslated (today's `*)` branch).

### 3. Certificate lifecycle — `recert.sh` is mode-aware

The lifecycle (issue → store → deploy → detect expiry → renew → reload) has a
**different owner per mode**. `recert.sh` reads the persisted `SSL_MODE` and does
the right thing — it is **not** a single Let's-Encrypt renew routine. Today
`setup_cert_renewal` is wired *solely* from the LE path, which means **a
self-signed cert silently expires at 365 days with nothing to renew it** — a real
lifecycle gap this convergence closes.

| Stage | `selfsigned` | `letsencrypt` | `manual` (BYO) | `offload` |
|-------|--------------|---------------|----------------|-----------|
| Issue | `openssl` at init | acme.sh DNS-01 / certbot HTTP-01 | operator supplies | **upstream proxy** |
| Store | `certs/` | `certs/` | `certs/` | n/a |
| Renew | **regenerate when near expiry** | acme.sh `--renew` (~60d) | operator re-supplies | upstream |
| Expiry detect | timer checks `enddate` | acme.sh + timer safety net | timer checks, **warn only** | n/a |
| On failure | local — cannot fail | fall back to `selfsigned` (existing behavior) | keep serving old cert, warn loudly | n/a |
| Reload | reload web container after any change | same | same | n/a |

The ownership split, stated plainly:

- **`selfsigned` / `letsencrypt`** — the appliance **fully self-manages** the
  lifecycle (issue + renew + reload). Self-contained.
- **`manual` (BYO)** — the operator owns issuance and renewal; the appliance only
  **monitors and warns** near expiry (it has no CA/key authority to mint a
  replacement) and **never overwrites** a BYO cert.
- **`offload`** — **upstream owns the entire lifecycle**; `recert.sh` is a
  **no-op that returns success**. The appliance speaks plain HTTP and never holds
  a cert. (This is the "it's upstream, we don't manage it" case.)

Expiry detection reuses install.sh's existing `check_existing_acme_cert` /
`show_cert_info` (openssl `enddate` parsing), generalized across modes.
*Scheduling* stays path-appropriate and out of the shared lib — `install.sh`'s
cron stays cron, the appliance uses a systemd timer (it has systemd) — but both
invoke the one `recert.sh`, and `operator.sh recert` runs it on demand. This makes
`operator.sh recert` real.

### 4. Offload as a first-class contract: `EXTERNAL_URL`

"Behind a reverse proxy" is supported as a mode whose **contract** is:

- The operator declares the public URL **including scheme** —
  `EXTERNAL_URL=https://kg.example.com` — not a bare hostname.
- The app serves plain HTTP internally but derives **scheme-sensitive** outputs
  (OAuth `redirect_uri`, absolute links, `Secure` cookies, HSTS) from
  `EXTERNAL_URL`, and trusts `X-Forwarded-Proto/Host/For`.

Concretely: introduce `EXTERNAL_URL` (deriving scheme + host; `WEB_HOSTNAME`
remains the host-only input for backward compat / non-TLS), and fix
`headless-init.sh:496` and the API-side OAuth client registration to use the
`EXTERNAL_URL` scheme instead of a literal `http://`. This is the canonical
GitLab `external_url https://… + listen_https=false` pattern.

### Out of scope

- **macvlan / host-shim** stays an `install.sh`-only concern (ADR-104 lists it
  separately). The maintainer is moving the reference host (cube) *away* from the
  macvlan second-IP approach toward self-contained services, so the converged
  appliance path does **not** grow a macvlan dependency. Deprecating the shim is
  a later, separate decision.
- The **first-run claim protocol** (ADR-104) is orthogonal; cert mode is chosen
  at provision time, claim happens at first visit.

## Consequences

### Positive

- One code path for certs, reachable from every install path; the appliance and
  `operator.sh init` gain HTTPS they never had.
- `operator.sh recert` stops being a broken command, and becomes **mode-aware**:
  it closes the silent self-signed-expiry gap, renews LE, warns on BYO, and
  no-ops on offload — so every mode has a defined lifecycle owner.
- New DNS providers become data, not code.
- The `http://`-redirect bug — latent for every TLS deployment — is fixed at the
  contract level, not patched per-call.
- Self-signed default means the appliance is HTTPS-capable out of the box.

### Negative

- `install.sh`'s large SSL section must be refactored without regressing existing
  production installs (cube's prior install proved the current path works). The
  extraction must be behavior-preserving and tested against `install.sh` first.
- `EXTERNAL_URL` touches the API's OAuth client registration, not just scripts —
  a slightly wider blast radius than a pure installer refactor.

### Neutral

- acme.sh remains the issuance engine for DNS-01; certbot for HTTP-01. No new
  cert tooling is introduced — only its invocation is relocated and parameterized.
- The four-mode taxonomy is unchanged from what `install.sh` already exposes;
  this ADR moves and generalizes it, it does not redesign it.

## Alternatives Considered

- **Leave certs in `install.sh`, point operator users at it.** Rejected: it
  cements the two-installers split ADR-104 is dismantling and leaves the
  appliance permanently HTTP-only.
- **Offload-only (always require an external proxy).** Rejected: violates
  "appliance handles itself"; many targets (cube, going self-contained) have no
  proxy and shouldn't be forced to run one.
- **Auto-detect a fronting proxy.** Rejected: unreliable; an explicit
  `EXTERNAL_URL` + mode is the convention (GitLab/Nextcloud/Authentik) precisely
  because guessing the public scheme is a footgun.
- **Bundle macvlan into the shared lib too.** Rejected for now: the reference
  host is moving off it; pulling it into the converged path would spread a
  capability we're trying to retire.

## Migration Note (non-binding sketch)

Incremental, each step shippable:

1. Extract `operator/lib/configure-ssl.sh` from `install.sh` SECTION 9;
   `install.sh` sources it (pure consolidation, no behavior change). Verify
   `install.sh` still produces identical artifacts.
2. Replace the DNS `case` with the provider registry inside the shared lib.
3. Implement mode-aware `operator/lib/recert.sh` (self-signed regen near expiry,
   LE renew, BYO warn-only, offload no-op) + expiry detection; `operator.sh
   recert` now works. Wire scheduling per path (install.sh cron / appliance
   systemd timer).
4. Add `--ssl*` flags to `headless-init.sh` + `guided-init.sh`; operator init can
   now stand up TLS.
5. Introduce `EXTERNAL_URL`; fix `redirect_uri` scheme in `headless-init.sh` and
   API OAuth client registration; honor `X-Forwarded-Proto`.
6. Deploy cube self-contained (selfsigned or porkbun DNS-01) on the converged
   path as the first real exercise of operator-init TLS.
