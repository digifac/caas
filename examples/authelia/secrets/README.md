# Secrets Directory

This directory contains secret files used by Authelia.
Generate them with the following commands:

```bash
# JWT secret (32+ random bytes)
openssl rand -hex 32 > jwt_secret.txt

# Session secret (32+ random bytes)
openssl rand -hex 32 > session_secret.txt

# Storage encryption key (32+ random bytes)
openssl rand -hex 32 > storage_key.txt
```

These files are referenced in `docker-compose.yml` as Docker secrets.
