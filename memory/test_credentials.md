# Test Credentials

## Dashboard Login
- **URL**: https://f91ea9ce-4f4b-4aed-87d3-4af955922294.preview.emergentagent.com
- **Username**: `admin1`
- **Password**: `pwd1`

Auth mechanism: JWT (HS256), 24 hour expiry. Issued by POST `/api/login`.
Credentials configurable via backend env vars `ADMIN_USER` / `ADMIN_PASS`.

## Google SSO
Not configured in this environment (GOOGLE_CLIENT_ID is empty). The SSO button
in the login UI is hidden when no client id is configured.
