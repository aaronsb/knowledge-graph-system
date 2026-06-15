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
| `private` | appliance VM on a trusted LAN, private IP | in-VM Traefik | `manual` (preferred) or `selfsigned` |
| `internet` | VM with a public IP, `:443` reachable | in-VM Traefik | `letsencrypt` |
| `proxied` | behind an edge load balancer or proxy | edge | `offload` |
| `public-nat` | public IP behind NAT or Cloudflare | in-VM Traefik or tunnel | DNS-01 delegation or `offload` |

## TLS modes

Four modes map to Traefik `certResolver` configurations:

| Mode | Mechanism | Who renews |
|------|-----------|------------|
| `selfsigned` | Traefik's built-in default cert | Traefik (automatic) |
| `letsencrypt` | Traefik ACME resolver — TLS-ALPN-01 by default | Traefik (automatic) |
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

`--tls=selfsigned`, `--tls=manual`, and `--tls=letsencrypt` require `--router=traefik`. `--tls=letsencrypt` requires `--le-email`. No restart is needed after init — the modes are composable overlays selected at startup.

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

## DNS-01 via lego (opt-in, private-only)

Traefik ships lego, which supports ~100 DNS providers natively. DNS-01 is useful when `:80` and `:443` are not publicly reachable (e.g., NAT or Cloudflare proxy). It is **opt-in and restricted to private deployments** because it requires an account-wide DNS credential on the appliance (porkbun keys are not per-zone scoped — see ADR-105 §7 for the trust posture).

To enable DNS-01, edit `docker/docker-compose.traefik-tls-letsencrypt.yml` and replace the `tlsChallenge` resolver flags with:

```yaml
- --certificatesresolvers.le.acme.dnschallenge=true
- --certificatesresolvers.le.acme.dnschallenge.provider=porkbun
```

Then add the provider credentials to the Traefik environment:

```bash
PORKBUN_API_KEY=pk1_...
PORKBUN_SECRET_API_KEY=sk1_...
```

For other providers, substitute the lego provider name and its required environment variables. The [lego documentation](https://go-acme.github.io/lego/dns/) lists all supported providers.

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
