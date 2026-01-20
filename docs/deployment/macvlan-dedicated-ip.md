# Macvlan Deployment Pattern: Dedicated LAN IP

Deploy Knowledge Graph with its own LAN IP address, avoiding port conflicts with the host.

## When to Use This Pattern

- Host ports 80/443 are already in use (e.g., traefik, other services)
- You want the service to appear as a separate host on your LAN
- Multiple services need the same ports without reverse proxy complexity
- Direct LAN access is preferred over port forwarding

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                        Physical LAN                         │
│                     192.168.1.0/24                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Docker Host              Knowledge Graph                  │
│   192.168.1.10             192.168.1.20                     │
│   ├── traefik:80/443       └── kg-web:80/443               │
│   ├── other apps               ├── HTTPS termination       │
│   └── ...                      └── Proxies to kg-api       │
│                                                             │
│   Both appear as separate hosts on the LAN                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The macvlan driver creates a virtual network interface that connects directly to your physical network, giving the container its own MAC address and IP.

## Setup

### 1. Create the Macvlan Network

```bash
# Identify your physical interface
ip link show  # e.g., eno1, eth0, enp0s3

# Create macvlan network
docker network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  -o parent=eno1 \
  lannet
```

Adjust subnet, gateway, and parent interface for your network.

### 2. Create SSL Compose Overlay

Create `docker-compose.ssl.yml` alongside the main compose file:

```yaml
services:
  web:
    networks:
      default:        # Keep internal network for API communication
      lannet:         # Add macvlan for external access
        ipv4_address: 192.168.1.20  # Your dedicated IP
    ports: []         # Clear port mappings - not needed with dedicated IP
    volumes:
      - ./nginx.ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1/health"]
      interval: 30s
      timeout: 3s
      retries: 3

networks:
  lannet:
    external: true
```

### 3. Configure nginx for SSL

Create `nginx.ssl.conf`:

```nginx
# Redirect HTTP to HTTPS (except healthcheck)
server {
    listen 80;
    server_name kg.example.com;

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl;
    http2 on;
    server_name kg.example.com;
    root /usr/share/nginx/html;
    index index.html;

    ssl_certificate /etc/nginx/certs/kg.example.com.fullchain.cer;
    ssl_certificate_key /etc/nginx/certs/kg.example.com.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    add_header Strict-Transport-Security "max-age=31536000" always;

    gzip on;
    gzip_types text/plain text/css application/javascript application/json;

    # Static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy API requests
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

### 4. Obtain SSL Certificates

For hosts behind NAT/firewall, use DNS-01 challenge with acme.sh:

```bash
# Install acme.sh
curl https://get.acme.sh | sh

# Set DNS provider credentials (example: Porkbun)
export PORKBUN_API_KEY="pk1_..."
export PORKBUN_SECRET_API_KEY="sk1_..."

# Issue certificate
~/.acme.sh/acme.sh --issue \
  --dns dns_porkbun \
  -d kg.example.com

# Install to certs directory
~/.acme.sh/acme.sh --install-cert -d kg.example.com \
  --key-file ./certs/kg.example.com.key \
  --fullchain-file ./certs/kg.example.com.fullchain.cer
```

Supported DNS providers: Cloudflare, Porkbun, Route53, DigitalOcean, and [many more](https://github.com/acmesh-official/acme.sh/wiki/dnsapi).

### 5. Start with SSL Overlay

```bash
# Include the SSL overlay in your compose stack
docker compose -f docker-compose.yml \
               -f docker-compose.prod.yml \
               -f docker-compose.ghcr.yml \
               -f docker-compose.ssl.yml \
               up -d
```

## DNS Configuration

Point your hostname to the dedicated IP:

| Type | Name | Value |
|------|------|-------|
| A | kg.example.com | 192.168.1.20 |

For local-only access, add to `/etc/hosts` or your local DNS server.

## Troubleshooting

### Container can't reach the internet

Macvlan containers can't communicate with the host by default. If you need the container to reach services on the host:

```bash
# Create a macvlan interface on the host
ip link add macvlan0 link eno1 type macvlan mode bridge
ip addr add 192.168.1.19/32 dev macvlan0  # Adjacent IP for host-side
ip link set macvlan0 up
ip route add 192.168.1.20/32 dev macvlan0  # Route to container IP
```

### IP address conflicts

Ensure the dedicated IP (e.g., 192.168.1.20) is:
- Outside your DHCP range
- Not used by any other device
- Reserved in your router if possible

### Healthcheck failures

The Docker healthcheck runs from inside the container. With SSL, it must use HTTP on localhost (not the external HTTPS URL):

```yaml
healthcheck:
  test: ["CMD", "wget", "--spider", "http://127.0.0.1/health"]
```

## Comparison with Other Patterns

| Pattern | Use Case | Complexity |
|---------|----------|------------|
| **Macvlan (this)** | Dedicated IP, port 80/443 already used | Medium |
| **Host ports** | Simple single-service host | Low |
| **Reverse proxy** | Multiple services, single IP | Medium-High |
| **SSL offload** | Behind existing reverse proxy | Low |

## Related

- [install.sh SSL options](../installation.md) - `--ssl letsencrypt --ssl-dns`
- [acme.sh DNS API](https://github.com/acmesh-official/acme.sh/wiki/dnsapi)
- [Docker macvlan docs](https://docs.docker.com/network/drivers/macvlan/)
