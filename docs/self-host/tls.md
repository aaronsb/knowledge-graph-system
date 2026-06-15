---
id: 1.O.07
domain: infra
mode: operations
---

# TLS and Certificates

Kappa Graph uses Traefik as its in-VM router and TLS terminator. The cert posture is driven by a deployment scenario — you declare where the appliance runs, and `operator.sh init` derives the right mode. The full design rationale is in [ADR-105](../architecture/infrastructure/ADR-105-scenario-driven-tls-via-in-vm-traefik-router.md).

## Deployment scenarios

| Scenario | Where it runs | TLS terminator | Default cert mode |
|----------|--------------|----------------|-------------------|
| `dev` | containers on a dev box, no VM | none | HTTP only |
| `private` | appliance VM on a trusted LAN, private IP | in-VM Traefik | `letsencrypt` + `dns-01` (self-renewing), or `selfsigned` / `manual` |
| `internet` | VM with a public IP, `:443` reachable | in-VM Traefik | `letsencrypt` (TLS-ALPN-01) |
| `proxied` | behind an edge load balancer or proxy | edge | `offload` |
| `public-nat` | public IP behind NAT or Cloudflare | in-VM Traefik or tunnel | `letsencrypt` + `dns-01`, or `offload` |

## TLS modes

Four modes map to Traefik `certResolver` configurations:

| Mode | Mechanism | Who renews |
|------|-----------|------------|
| `selfsigned` | Traefik's built-in default cert | Traefik (automatic) |
| `letsencrypt` | Traefik ACME resolver — TLS-ALPN-01 (default) or DNS-01 via `--acme-challenge` | Traefik (automatic) |
| `manual` | Traefik file provider, operator-supplied cert | Operator re-supplies; Traefik hot-reloads |
| `offload` | HTTP in-VM; edge proxy terminates TLS | Upstream (recert is a no-op) |

`selfsigned` is the default when you enable Traefik without specifying a mode. It requires no credentials and no DNS access.

## Configure TLS during init

Pass `--router=traefik` and `--tls=<mode>` to `operator.sh init --headless`:

```bash
# Self-signed (no credentials needed — good for trusted LAN)
./operator.sh init --headless \
  --router=traefik \
  --tls=selfsigned \
  --web-hostname=kg.example.lan \
  ...

# Let's Encrypt via TLS-ALPN-01 (public IP, :443 reachable)
./operator.sh init --headless \
  --router=traefik \
  --tls=letsencrypt \
  --le-email=admin@example.com \
  --web-hostname=kg.example.com \
  ...

# Let's Encrypt via DNS-01 (PRIVATE box, no inbound :443 — self-renewing)
# PORKBUN_API_KEY / PORKBUN_SECRET_API_KEY must be in the environment.
./operator.sh init --headless \
  --router=traefik \
  --tls=letsencrypt \
  --acme-challenge=dns-01 \
  --dns-provider=porkbun \
  --le-email=admin@example.com \
  --external-url=https://kg.example.com \
  ...

# Operator-supplied cert (manual mode)
./operator.sh init --headless \
  --router=traefik \
  --tls=manual \
  --web-hostname=kg.example.com \
  ...

# Edge proxy terminates TLS (offload)
./operator.sh init --headless \
  --router=traefik \
  --tls=offload \
  --external-url=https://kg.example.com \
  --web-hostname=kg.example.com \
  ...
```

`--tls=selfsigned`, `--tls=manual`, and `--tls=letsencrypt` require `--router=traefik`. `--tls=letsencrypt` requires `--le-email`. `--acme-challenge=dns-01` requires `--tls=letsencrypt` and the DNS provider's credentials in the environment (porkbun: `PORKBUN_API_KEY` + `PORKBUN_SECRET_API_KEY`). No restart is needed after init — the modes are composable overlays selected at startup.

`--external-url` sets the scheme+host the app uses for OAuth redirect URIs, cookie domains, and frontend links. When `--tls` is set and `--external-url` is omitted, init derives it as `https://<web-hostname>` automatically.

## Selfsigned mode

Traefik serves its built-in default certificate. No credentials, no renewal steps. Browsers will show a trust warning; accept it or add the cert to your system trust store. Use this on a private network where you control client trust or where a browser warning is acceptable.

## Let's Encrypt mode (TLS-ALPN-01)

Traefik obtains and auto-renews a certificate from Let's Encrypt using TLS-ALPN-01. The appliance needs `:443` reachable from the internet. No DNS credential is required.

```bash
# Verify issuance and renewal events in Traefik logs:
./operator.sh logs traefik | grep -i acme
```

If issuance fails, check that `:443` is open in your firewall and that `--web-hostname` resolves to the appliance's public IP.

**Testing against staging:** Set `LE_CASERVER` in `.env` before starting to hit Let's Encrypt staging and avoid rate limits:

```
LE_CASERVER=https://acme-staging-v02.api.letsencrypt.org/directory
```

Remove or unset it before going to production.

## Manual mode

The operator issues the certificate off-box and drops it into `docker/certs/` (or the path in `KG_CERT_DIR`). Traefik's file provider serves it and hot-reloads on replacement — no restart required.

```
docker/certs/
├── tls.crt   # PEM full-chain
└── tls.key   # PEM private key
```

Issue the cert by any means: `acme.sh` + porkbun DNS-01 on a separate host, an internal CA, a purchased cert. This is the recommended posture when the appliance is on a network where you do not want a DNS credential present on the box.

To check cert status:

```bash
./operator.sh recert
```

`recert` reads `TLS_MODE` from `.operator.conf`, verifies the cert files exist, reports expiry, and warns within 21 days of expiry. It does not renew — renewal is the operator's responsibility for this mode.

To replace an expiring cert, copy the new `tls.crt` and `tls.key` into `docker/certs/` (or `KG_CERT_DIR`). Traefik picks it up within seconds without a restart.

## Let's Encrypt via DNS-01 (private box, self-renewing)

TLS-ALPN-01 and HTTP-01 require Let's Encrypt to reach the box from the internet on `:443`/`:80`. A **private** deployment (RFC-1918 address, no inbound NAT) cannot satisfy them. DNS-01 proves control of the name by writing a TXT record, so it is the **only** ACME challenge that works for a private box with a public DNS name — and it auto-renews in-container, the converged equivalent of the old `install.sh` acme.sh+porkbun flow.

It is a selectable option on `letsencrypt`, not a file edit:

```bash
# In .env (read by Traefik/lego — written here automatically by init):
PORKBUN_API_KEY=pk1_...
PORKBUN_SECRET_API_KEY=sk1_...

./operator.sh init \
  --router=traefik \
  --tls=letsencrypt \
  --acme-challenge=dns-01 \
  --dns-provider=porkbun \
  --le-email=you@example.com \
  --external-url=https://kg.example.com
```

The operator reads `PORKBUN_API_KEY`/`PORKBUN_SECRET_API_KEY` from the environment (never the command line) and persists them to `.env`; Traefik's lego resolver does the DNS-01 dance and renews automatically. `operator.sh recert` is a no-op.

On the **appliance**, set the same via `provision.env` — declarative, no shell:

```ini
KG_EXTERNAL_URL=https://kg.example.com
KG_TLS_MODE=letsencrypt
KG_ACME_CHALLENGE=dns-01
KG_DNS_PROVIDER=porkbun
KG_LE_EMAIL=you@example.com
KG_PORKBUN_API_KEY=pk1_...
KG_PORKBUN_SECRET_API_KEY=sk1_...
```

**Trust posture (ADR-105 §7):** DNS-01 places an account-scoped DNS API credential inside the appliance — a real blast radius. Scope the porkbun key to the one zone where possible, and prefer DNS-01 only for private/trusted boxes; `tls-alpn-01` stays the default for internet-exposed boxes. lego ships ~100 providers ([docs](https://go-acme.github.io/lego/dns/)); porkbun is wired here. For another provider, set `--dns-provider` and add its env vars to `docker/docker-compose.traefik-tls-letsencrypt-dns.yml`.

## Offload mode

Use this when an edge proxy (nginx, Caddy, an ALB, Cloudflare) terminates TLS and forwards plain HTTP to the appliance. The appliance runs HTTP internally, and `EXTERNAL_URL` is the load-bearing variable that keeps OAuth redirects and frontend links correct.

```bash
# In .env (or pass as --external-url during init):
EXTERNAL_URL=https://kg.example.com
```

The edge must forward `X-Forwarded-Proto: https`, `X-Forwarded-Host`, and `X-Forwarded-For`. The app derives `redirect_uri` and cookie domains from `EXTERNAL_URL`, not from the incoming request.

`operator.sh recert` is a no-op in offload mode — cert lifecycle belongs to the upstream edge.

## Check and renew

```bash
# Report current TLS mode and cert status (all modes):
./operator.sh recert

# For letsencrypt — Traefik auto-renews; inspect logs:
./operator.sh logs traefik | grep -i acme

# For manual — replace cert files in docker/certs/, Traefik hot-reloads:
cp new.crt docker/certs/tls.crt
cp new.key docker/certs/tls.key
./operator.sh recert   # verify the replacement was picked up
```

## Topology

Every client (browser, kg CLI, FUSE driver, MCP server) reaches the platform through Traefik's single ingress. Traefik routes by path to `web`, `/api`, and `/mgmt`:

```
Browser / kg CLI / FUSE / MCP
         │
         ▼
  Traefik :80 / :443
  (TLS termination + routing)
         │
  ┌──────┼──────────┐
  ▼      ▼          ▼
 web   /api       /mgmt
       api:8000
       │       │
  Postgres   Garage S3
```

This single ingress is what gives the CLI, FUSE driver, and MCP server a consistent endpoint regardless of which internal port each service uses.
