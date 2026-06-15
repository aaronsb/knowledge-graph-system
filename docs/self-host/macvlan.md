# Dedicated IP with macvlan

macvlan networking gives a Kappa Graph deployment its own MAC address and LAN IP, making the platform appear as a distinct host on your network. Use this when ports 80/443 on the Docker host are already in use, or when you want the service reachable at a stable LAN address without a reverse proxy in front of it.

## When to use this

- The Docker host runs Traefik, Caddy, or another service that already owns ports 80/443.
- You want `https://kg.example.com` to resolve directly to the container, not through the host.
- Multiple services need port 443 simultaneously on the same physical machine.

## How it works

```
┌──────────────────────────────────────────────────────────────┐
│                        Physical LAN                          │
│                      192.168.1.0/24                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   Docker Host               Kappa Graph                      │
│   192.168.1.10              192.168.1.82                     │
│   ├── traefik :80/443       └── kg-traefik :80/443           │
│   └── other services            (TLS terminated by Traefik)  │
│                                                              │
│   Both appear as separate hosts on the LAN.                  │
└──────────────────────────────────────────────────────────────┘
```

The macvlan driver creates a virtual network interface backed by your physical NIC. The container gets its own MAC address and IP; the host kernel bridges traffic at layer 2.

**Limitation:** macvlan containers cannot communicate with the Docker host over the same interface. Access the platform from any other device on the LAN. See [Host-to-container routing](#host-to-container-routing) if you need the host to reach the container.

## Prerequisites

- Linux host with Docker installed
- A physical NIC with a known interface name (`eno1`, `eth0`, etc.)
- A static IP address outside your DHCP range, or a DHCP reservation
- A DNS A record pointing your hostname to that static IP
- A domain with a DNS provider that supports DNS-01 challenge if the host is behind NAT (Porkbun, Cloudflare, and [~100 others](https://go-acme.github.io/lego/dns/) are supported)

## Network planning

Decide these values before running any commands:

| Item | Example | Notes |
|---|---|---|
| Parent interface | `eno1` | Run `ip link show` to find yours |
| Subnet | `192.168.1.0/24` | Your LAN subnet |
| Gateway | `192.168.1.1` | Your router |
| Static IP | `192.168.1.82` | Must be outside DHCP range |
| Hostname | `kg.example.com` | DNS A record pointing to the static IP |

Use a static IP, not DHCP. Docker generates a random MAC for each container on secondary networks, so DHCP reservations tied to a MAC address will not get a consistent assignment.

## Step 1 — Create the macvlan network

```bash
docker network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  -o parent=eno1 \
  lannet
```

Adjust `--subnet`, `--gateway`, and `-o parent` for your network. The network name `lannet` matches the `external: true` entry in `docker/docker-compose.prod.yml`.

## Step 2 — Configure the static IP

`docker/docker-compose.prod.yml` already includes the `lannet` macvlan attachment for the `web` service with a placeholder IP. Edit it to match your planned static IP:

```yaml
# docker/docker-compose.prod.yml (excerpt)
services:
  web:
    networks:
      kg-internal:
      lannet:
        ipv4_address: 192.168.1.82   # ← your static IP

networks:
  lannet:
    external: true
```

No other compose file needs editing; the `ports:` mappings in the base `docker-compose.yml` are irrelevant once the container has a direct LAN IP.

## Step 3 — Enable TLS with Traefik

Kappa Graph uses Traefik as its internal router (ADR-105). Set `ROUTER_MODE` and `TLS_MODE` in your `.operator.conf` file (located in the project root):

```bash
# .operator.conf
ROUTER_MODE=traefik
TLS_MODE=letsencrypt
LE_EMAIL=admin@example.com
EXTERNAL_URL=https://kg.example.com
```

`operator.sh` reads this file at startup and selects the matching compose overlays:

| `TLS_MODE` | Overlays added | Effect |
|---|---|---|
| `none` | (none) | HTTP only, no redirect |
| `selfsigned` | `traefik-tls.yml` | HTTPS with Traefik's built-in self-signed cert |
| `letsencrypt` | `traefik-tls.yml` + `traefik-tls-letsencrypt.yml` | HTTPS with auto-renewed Let's Encrypt cert (TLS-ALPN-01) |
| `manual` | `traefik-tls.yml` + `traefik-tls-manual.yml` | HTTPS with a certificate you supply |

For TLS-ALPN-01 (`letsencrypt` mode), port 443 must be reachable from the public internet. If the host is behind NAT, use DNS-01 instead — see [DNS-01 challenge for NAT hosts](#dns-01-challenge-for-nat-hosts).

## Step 4 — Create the DNS record

Point your hostname to the static IP at your DNS provider:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | kg | 192.168.1.82 | 300 |

For `kg.example.com`, enter `kg` as the record name under the `example.com` zone. For local-only access, add an entry to `/etc/hosts` or your local DNS resolver instead.

## Step 5 — Start the platform

```bash
./operator.sh start
```

Traefik obtains the certificate on first startup and stores it under `./acme/acme.json` (or the path set by `KG_ACME_DIR`). Renewal is automatic.

## Verify the deployment

Run these checks from a device other than the Docker host:

```bash
# Check container health
./operator.sh status

# Confirm macvlan IP assignment
docker inspect kg-web \
  --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}: {{$v.IPAddress}}{{"\n"}}{{end}}'

# Test HTTPS from another LAN host
curl -s https://kg.example.com/health
```

The health endpoint returns `healthy` when the platform is up.

## DNS-01 challenge for NAT hosts

When port 443 is not reachable from the public internet, TLS-ALPN-01 cannot complete. Use DNS-01 instead: the challenge is answered by adding a DNS TXT record, so no inbound port is required.

DNS-01 is opt-in. It requires placing DNS provider credentials in the Traefik container environment. Edit `docker/docker-compose.traefik-tls-letsencrypt.yml` to switch the resolver from `tlschallenge` to `dnschallenge`:

```yaml
# In the traefik service command, replace:
- --certificatesresolvers.le.acme.tlschallenge=true
# with:
- --certificatesresolvers.le.acme.dnschallenge=true
- --certificatesresolvers.le.acme.dnschallenge.provider=porkbun
```

Then pass the provider credentials via environment variables in the same overlay:

```yaml
services:
  traefik:
    environment:
      PORKBUN_API_KEY: ${PORKBUN_API_KEY}
      PORKBUN_SECRET_API_KEY: ${PORKBUN_SECRET_API_KEY}
```

Set those variables in `.env` before starting. Provider names and their expected environment variables are listed in the [lego DNS provider docs](https://go-acme.github.io/lego/dns/).

For hosts that prefer to issue certificates off-box, use `TLS_MODE=manual` and mount the cert files — see [TLS and Certificates](tls.md).

## Host-to-container routing

macvlan containers are isolated from the Docker host at layer 2. If you need the host to reach the container (for example, to run `curl` health checks from the host itself), add a macvlan interface on the host:

```bash
# Create a host-side macvlan interface on an adjacent IP
ip link add macvlan0 link eno1 type macvlan mode bridge
ip addr add 192.168.1.83/32 dev macvlan0
ip link set macvlan0 up

# Route traffic to the container IP through it
ip route add 192.168.1.82/32 dev macvlan0
```

Replace `192.168.1.83` with any unused IP adjacent to your container's address. This route is not persistent across reboots — add it to your network manager or a systemd unit if you need it permanently.

## Troubleshooting

### Container gets the wrong IP or no IP

Static assignment via `ipv4_address` in the compose file is the reliable path. If the container is using DHCP (no `ipv4_address` set), Docker's randomly generated MAC will not match any DHCP reservation. Set the IP statically in `docker-compose.prod.yml` and recreate the container:

```bash
./operator.sh stop
./operator.sh start
```

### Certificate is not issuing

Check Traefik logs for ACME errors:

```bash
./operator.sh logs traefik
```

For DNS-01: confirm the provider credentials are set and the DNS TXT record appears before the validation timeout. Use Let's Encrypt's staging CA while testing to avoid rate limits — set `LE_CASERVER=https://acme-staging-v02.api.letsencrypt.org/directory` in `.operator.conf`.

### Host cannot reach the container

Expected behavior with macvlan. Add a host-side macvlan interface as described above, or test from another device on the LAN.

### Container won't start

```bash
./operator.sh logs web
docker inspect kg-web --format '{{.State.Error}}'
```

The most common cause is an IP conflict — another device on the LAN already holds `192.168.1.82`. Confirm the IP is free before assigning it.
