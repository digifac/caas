# Nginx + Let's Encrypt Configuration

This example shows how to deploy CAAS behind Nginx with:

- **TLS termination** using Let's Encrypt certificates (via `certbot`)
- **API key authentication** enforced by Nginx before requests reach the application

## Directory Structure

```
nginx-letsencrypt/
├── nginx.conf         # Nginx configuration
├── docker-compose.yml # Full stack: Nginx + CAAS + Certbot
├── .env.example       # Required environment variables
└── README.md
```

## Prerequisites

- Domain name pointing to your server (e.g., `caas.example.com`)
- Docker & Docker Compose installed
- Ports `80` and `443` open and available

## Quick Start

### 1. Set Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Domain
DOMAIN=caas.example.com

# Email for Let's Encrypt
CERTBOT_EMAIL=admin@example.com

# API Key — choose a strong random value
#   Example: openssl rand -hex 32
CAAS_API_KEY=your-secret-api-key-here
```

### 2. Start the Stack

```bash
docker compose up -d
```

This will:

1. Start Nginx on ports 80/443
2. Run Certbot to obtain a Let's Encrypt certificate for your domain
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

- Nginx listens on port 443 and terminates TLS
- Certbot uses the `http-01` challenge through Nginx's `/.well-known/acme-challenge/` location on port 80
- Certificates are stored in `/etc/letsencrypt/live/` via a Docker volume
- A loop inside the Certbot container checks for renewal every 12 hours
- On renewal, Nginx is reloaded automatically via the deploy-hook

### API Key Authentication

- Nginx uses a `map` block to compare the `X-API-Key` header against the configured secret
- If the header is missing or doesn't match, Nginx returns `401 Unauthorized`
- Valid requests are forwarded to the CAAS container with the `X-API-Key` header stripped
- The CAAS application never sees the API key — Nginx handles it entirely

## Production Notes

- Increase `worker_connections` in Nginx based on expected traffic
- Add `limit_req_zone` for rate limiting at the proxy level
- Consider adding a `stub_status` server block for monitoring
- Monitor certificate renewal logs: `docker compose logs certbot`
