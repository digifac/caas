# HAProxy + Let's Encrypt Configuration

This example shows how to deploy CAAS behind HAProxy with:

- **TLS termination** using Let's Encrypt certificates (via `certbot`)
- **API key authentication** enforced by HAProxy before requests reach the application

## Directory Structure

```
haproxy-letsencrypt/
├── haproxy.cfg          # HAProxy configuration
├── docker-compose.yml   # Full stack: HAProxy + CAAS + Certbot
├── certbot/
│   └── entrypoint.sh    # Certbot certificate renewal hook
└── README.md
```

## Prerequisites

- Domain name pointing to your server (e.g., `caas.example.com`)
- Docker & Docker Compose installed
- Ports `80` and `443` open and available

## Quick Start

### 1. Set Environment Variables

Create a `.env` file in this directory:

```env
# Domain
DOMAIN=caas.example.com

# API Key — choose a strong random value
#   Example: openssl rand -hex 32
CAAS_API_KEY=your-secret-api-key-here

# CAAS settings (passed through to the CAAS container)
CAAS_HOST=0.0.0.0
CAAS_PORT=8000
```

### 2. Start the Stack

```bash
docker compose up -d
```

This will:

1. Start HAProxy on ports 80/443 with a self-signed temporary certificate
2. Run Certbot to obtain a real Let's Encrypt certificate for your domain
3. Start the CAAS container on port 8000 (internal network only)

### 3. Verify

```bash
# Without API key → 401 Unauthorized
curl -k https://caas.example.com/

# With API key → 200 OK
curl -k -H "X-API-Key: your-secret-api-key-here" https://caas.example.com/
```

## How It Works

### TLS / Let's Encrypt

- HAProxy listens on port 443 and terminates TLS
- Certbot uses the `http-01` challenge through HAProxy's `acme-challenge` frontend
- Certificates are stored in `/etc/letsencrypt/live/` inside the Certbot volume
- A cron job inside the Certbot container renews certificates every 12 hours
- On renewal, HAProxy is reloaded automatically via the deploy-hook

### API Key Authentication

- HAProxy inspects the `X-API-Key` header on every request to the CAAS backend
- If the header is missing or doesn't match, HAProxy returns `401 Unauthorized`
- Valid requests are forwarded to the CAAS container with the header stripped
- This means the CAAS application never sees the API key — HAProxy handles it entirely

## Production Notes

- Replace the temporary self-signed certificate flow with pre-provisioned certs if preferred
- Increase `maxconn` in HAProxy based on expected traffic
- Add `rate-limit` ACLs in HAProxy for additional protection
- Monitor certificate renewal logs: `docker compose logs certbot`
