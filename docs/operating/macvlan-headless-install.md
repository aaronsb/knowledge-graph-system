# Headless Installation with Macvlan Networking

Deploy the Knowledge Graph platform on a dedicated LAN IP using macvlan, with automated SSL via DNS-01 challenge.

## When to Use This Guide

- Docker host where ports 80/443 are already in use
- You want the platform on its own LAN IP (appears as separate device)
- Headless (non-interactive) automated setup
- Let's Encrypt SSL via DNS-01 challenge (works behind NAT/firewall)
- Cloud AI provider (OpenAI/Anthropic) for extraction

## Prerequisites

- Linux host with Docker installed
- Existing macvlan Docker network (or create during install)
- Domain with DNS provider supporting DNS-01 (Porkbun, Cloudflare, etc.)
- API keys: DNS provider + AI provider (OpenAI/Anthropic)

## Network Planning

Before installing, plan your network configuration:

| Item | Example | Notes |
|------|---------|-------|
| Parent interface | `eno1` | Physical NIC on your host |
| Subnet | `192.168.1.0/24` | Your LAN subnet |
| Gateway | `192.168.1.1` | Your router |
| Static IP | `192.168.1.82` | Must be outside DHCP range or reserved |
| Hostname | `kg.example.com` | DNS A record pointing to static IP |

**Important:** Use a static IP, not DHCP. Docker's `mac_address` option doesn't work reliably with multi-network containers, so DHCP reservations won't get consistent MACs.

## Create Macvlan Network

If you don't have an existing macvlan network:

```bash
docker network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  -o parent=eno1 \
  kg-macvlan
```

Or let install.sh create it with `--macvlan-create` flags.

## Full Headless Install Command

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash -s -- \
  --hostname kg.example.com \
  --ssl letsencrypt \
  --ssl-email admin@example.com \
  --ssl-dns dns_porkbun \
  --ssl-dns-key "$PORKBUN_API_KEY" \
  --ssl-dns-secret "$PORKBUN_SECRET_KEY" \
  --macvlan \
  --gpu nvidia \
  --ai-provider openai \
  --ai-key "$OPENAI_API_KEY"
```

### Flag Reference

| Flag | Description |
|------|-------------|
| `--hostname` | Public hostname (must have DNS pointing to your IP) |
| `--ssl letsencrypt` | Use Let's Encrypt for certificates |
| `--ssl-email` | Email for Let's Encrypt registration |
| `--ssl-dns dns_porkbun` | DNS provider for DNS-01 challenge |
| `--ssl-dns-key` | DNS provider API key |
| `--ssl-dns-secret` | DNS provider API secret (if required) |
| `--macvlan` | Use existing `kg-macvlan` network |
| `--gpu nvidia` | Enable NVIDIA GPU support (or `amd`, `cpu`) |
| `--ai-provider openai` | AI extraction provider (`openai`, `anthropic`, `ollama`) |
| `--ai-key` | API key for the AI provider |

### Creating Macvlan During Install

If no `kg-macvlan` network exists, use `--macvlan-create`:

```bash
curl -fsSL .../install.sh | bash -s -- \
  --hostname kg.example.com \
  --macvlan-create \
  --macvlan-parent eno1 \
  --macvlan-subnet 192.168.1.0/24 \
  --macvlan-gateway 192.168.1.1 \
  --ssl letsencrypt \
  --ssl-email admin@example.com \
  --ssl-dns dns_porkbun \
  --ssl-dns-key "$PORKBUN_API_KEY" \
  --ssl-dns-secret "$PORKBUN_SECRET_KEY" \
  --skip-ai
```

## Post-Install: Set Static IP

The installer generates a compose overlay that initially uses DHCP. For reliable operation, update it to use a static IP:

Edit `~/knowledge-graph/docker-compose.ssl.yml`:

```yaml
services:
  web:
    networks:
      default:
      kg-macvlan:
        ipv4_address: 192.168.1.82  # Your static IP
    ports: []
    volumes:
      - ./nginx.ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro

networks:
  kg-macvlan:
    external: true
```

Then recreate the web container:

```bash
cd ~/knowledge-graph
./operator.sh stop
./operator.sh start
```

## DNS Configuration

Create an A record pointing your hostname to the static IP:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | kg | 192.168.1.82 | 300 |

For `kg.example.com`, the DNS provider shows this as `kg` under the `example.com` domain.

## Verification

After installation completes:

```bash
# Check container status
cd ~/knowledge-graph
./operator.sh status

# Verify macvlan IP assignment
docker inspect kg-web --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}: {{$v.IPAddress}}{{"\n"}}{{end}}'

# Test from another host on the LAN (not the Docker host itself)
curl -sk https://kg.example.com/health
```

**Note:** The Docker host cannot directly reach containers on its own macvlan network. This is a [known macvlan limitation](https://docs.docker.com/network/drivers/macvlan/#macvlan-bridge-mode). Test from another device on your LAN.

## Troubleshooting

### Host Can't Reach Container

This is expected with macvlan. The host and its macvlan containers are isolated at layer 2. Access the platform from any other device on the network.

### Container Gets Wrong IP

Docker generates random MACs for secondary networks, breaking DHCP reservations. Use static IP assignment in the compose overlay instead (see Post-Install section above).

### Certificate Issues

Check acme.sh logs:

```bash
cat ~/.acme.sh/acme.sh.log
```

For DNS propagation issues, wait a few minutes and retry:

```bash
~/.acme.sh/acme.sh --issue --dns dns_porkbun -d kg.example.com --force
```

### Container Won't Start

Check logs:

```bash
./operator.sh logs web
docker inspect kg-web --format '{{.State.Error}}'
```

## Supported DNS Providers

The `--ssl-dns` flag accepts any [acme.sh DNS API](https://github.com/acmesh-official/acme.sh/wiki/dnsapi) provider:

| Provider | Flag Value | Key Variable | Secret Variable |
|----------|------------|--------------|-----------------|
| Porkbun | `dns_porkbun` | API Key | Secret Key |
| Cloudflare | `dns_cloudflare` | CF_Key | CF_Email |
| DigitalOcean | `dns_digitalocean` | DO_API_KEY | - |
| Gandi | `dns_gandi` | GANDI_LIVEDNS_KEY | - |
| Namecheap | `dns_namecheap` | API Key | Username |

## Related Documentation

- [Quick Start](quick-start.md) - Interactive and basic headless modes
- [Production Deployment](production.md) - HTTPS options and hardening
- [Configuration Reference](configuration.md) - All configuration options
