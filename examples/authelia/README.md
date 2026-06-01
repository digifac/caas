# Authelia + CAAS — Authentication Example

This example shows how to deploy CAAS behind Nginx with **Authelia** for user authentication.

## ✨ Features

- **User Authentication**: login page with username/password
- **2FA Support**: TOTP (Google Authenticator, Authy, etc.)
- **Session Management**: secure cookies with configurable expiration
- **Access Control**: fine-grained rules per route
- **LDAP Ready**: switch to Active Directory, OpenLDAP, etc.
- **TLS**: automatic HTTPS via Let's Encrypt
- **Zero code changes**: CAAS runs unchanged behind the proxy

## 📁 Directory Structure

```
authelia/
├── docker-compose.yml          # Full stack: Nginx + Authelia + CAAS + Certbot
├── .env.example                # Environment variables template
├── nginx/
│   └── nginx.conf              # Nginx config with Authelia integration
├── authelia/
│   ├── config.yml              # Authelia configuration
│   └── users_database.yml      # Local users (username, password hash, groups)
├── secrets/
│   └── README.md               # Instructions to generate secrets
└── README.md                   # This file
```

## 🏗️ Architecture

```
Client (browser, curl, app)
        │
        ▼
   ┌─────────┐
   │  Nginx  │  ← TLS termination (Let's Encrypt)
   │  :80/443│     Authelia enforcement (auth_request)
   └────┬────┘
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
   ┌──────────┐     ┌──────────┐      ┌──────────┐
   │ Authelia │     │   CAAS   │      │  Certbot │
   │  :9091   │     │  :8000   │      │  (TLS)   │
   └──────────┘     └──────────┘      └──────────┘
   - Login UI       - Conversion      - Cert renew
   - 2FA (TOTP)     - API endpoints   - Auto HTTPS
   - Sessions       - Web interface
   - Access rules
```

## 🚀 Quick Start

### 1. Prerequisites

- Domain name pointing to your server (e.g., `caas.example.com`)
- Docker & Docker Compose installed
- Ports `80` and `443` open and available

### 2. Generate Secrets

```bash
cd examples/authelia/secrets

# JWT secret
openssl rand -hex 32 > jwt_secret.txt

# Session secret
openssl rand -hex 32 > session_secret.txt

# Storage encryption key
openssl rand -hex 32 > storage_key.txt
```

### 3. Set Environment Variables

```bash
cd examples/authelia
cp .env.example .env
```

Edit `.env`:

```env
# Domain
DOMAIN=caas.example.com

# Email for Let's Encrypt
CERTBOT_EMAIL=admin@example.com

# Authelia TOTP issuer (shown in authenticator apps)
AUTHELIA_DUAL_FACTOR_TOTP_ISSUER=CAAS
```

### 4. Configure Users

Edit `authelia/users_database.yml` and set your passwords.

**Generate a password hash:**

```bash
docker run --rm authelia/authelia:latest hash-password 'your-secure-password'
```

**Replace the hash in the user entry:**

```yaml
users:
  admin:
    displayname: "Admin User"
    password: "$argon2id$v=19$m=65536,t=3,p=4$..." # ← paste your hash here
    email: admin@example.com
    groups:
      - admins
      - caas-users
```

### 5. Start the Stack

```bash
docker compose up -d
```

This will:

1. Start Nginx on ports 80/443
2. Start Authelia for authentication
3. Start CAAS on port 8000 (internal only)
4. Run Certbot to obtain a Let's Encrypt certificate

### 6. Access the Service

Navigate to `https://caas.example.com` — you'll be redirected to the Authelia login page.

After authentication, you'll have access to the CAAS web interface and API.

## 🔑 Usage

### Web Interface

Simply visit `https://caas.example.com` — Authelia handles the login flow automatically.

### API with curl

Authelia uses session cookies, so for API access you need to maintain a session:

```bash
# Step 1: Authenticate and get a session cookie
curl -v -c cookies.txt -X POST "https://caas.example.com/authelia/api/keys/csrf" \
  -H "Content-Type: application/json"

# Step 2: Login (this sets the session cookie)
curl -v -b cookies.txt -c cookies.txt -X POST "https://caas.example.com/authelia/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your-password"

# Step 3: Use the API with your session cookie
curl -v -b cookies.txt -X POST "https://caas.example.com/convert" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf"
```

### API with Browser

For browser-based clients, the session cookie is handled automatically after login. No extra configuration needed.

## 🔧 Configuration

### Access Control Rules

Edit `authelia/config.yml` → `access_control.rules` to customize which routes require authentication:

```yaml
access_control:
  default_policy: deny
  rules:
    - domain:
        - "${DOMAIN}"
      policy: one_factor
      rules:
        # No auth for health checks
        - path: /health
          policy: bypass

        # Auth required for API
        - path: /convert
          policy: one_factor

        # Auth required for web UI
        - path: /
          policy: one_factor
```

### Enable 2FA Enforcement

Change the dual factor mode in `authelia/config.yml`:

```yaml
dual_factor:
  mode: enforced # Mandatory for all users
```

### Switch to LDAP

In `authelia/config.yml`, comment out the `file` backend and uncomment the `ldap` block:

```yaml
authentication_backend:
  # file:
  #   path: /etc/authelia/users_database.yml
  ldap:
    url: ldap://your-ldap-server:389
    base_dn: dc=example,dc=com
    # ... see config.yml for full LDAP configuration
```

### Add Users

```bash
# Generate password hash
docker run --rm authelia/authelia:latest hash-password 'new-password'

# Add to authelia/users_database.yml
users:
  newuser:
    displayname: "New User"
    password: "$argon2id$v=19$m=65536,t=3,p=4$..."
    email: newuser@example.com
    groups:
      - caas-users
```

Then restart Authelia:

```bash
docker compose restart authelia
```

## 🔒 Security Notes

- **Secrets**: always generate unique secrets — never use the example values
- **Passwords**: use strong passwords and generate hashes with `authelia hash-password`
- **2FA**: enable `mode: enforced` in production for mandatory 2FA
- **TLS**: Let's Encrypt handles HTTPS automatically
- **Networks**: CAAS is only reachable via Nginx (internal Docker network)
- **Headers**: Authelia forwards user info via `X-Authelia-*` headers to CAAS

## 📊 Monitoring

```bash
# View logs
docker compose logs -f nginx
docker compose logs -f authelia
docker compose logs -f caas

# Check service health
docker compose ps

# View Authelia metrics (if enabled in config.yml)
curl http://localhost:9092/metrics
```

## 🆚 Comparison with Other Examples

| Feature            | API Key     | Authelia        |
| ------------------ | ----------- | --------------- |
| User login         | ❌          | ✅              |
| 2FA (TOTP)         | ❌          | ✅              |
| LDAP/AD support    | ❌          | ✅              |
| Session management | ❌          | ✅              |
| Login UI           | ❌          | ✅              |
| Password reset     | ❌          | ✅              |
| Role-based access  | ❌          | ✅ (via groups) |
| Machine-to-machine | ✅ (simple) | ✅ (OAuth2)     |
| Setup complexity   | ⭐ Low      | ⭐⭐ Medium     |

**Choose API Key** for simple machine-to-machine access.
**Choose Authelia** for human users with full authentication features.

## 🔗 Links

- [Authelia Documentation](https://www.authelia.com/docs/)
- [Authelia Configuration Reference](https://www.authelia.com/docs/configuration/)
- [Authelia Access Control](https://www.authelia.com/docs/configuration/access-control/)
- [CAAS Main README](../../README.md)
