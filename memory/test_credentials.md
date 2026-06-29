# Test Credentials

## Dashboard Login

### 1. Username / password (always works, fallback path)
- **Username:** `admin1`
- **Password:** `pwd1`
- (Overridable via `ADMIN_USER` / `ADMIN_PASS` env vars.)

### 2. Google SSO (when `GOOGLE_CLIENT_ID` is set in `/app/.env`)
- Domain allowlist: controlled by `ALLOWED_DOMAIN` in `.env`. Default `loreal.com`.
- Allowed test identities (in this env): any `@loreal.com` Google Workspace user.
- RBAC: all signed-in users currently have the same single role (full dashboard read).
  Per-user roles aren't enforced yet.
- No app-managed password — auth is delegated to Google.

### Auth flow notes
- Backend issues an HS256 JWT (24h TTL) after either path succeeds.
- Token is stored in `localStorage.token` and sent as `Authorization: Bearer ...`.
- `/api/auth/iap` is a stub here; it returns 401 outside of Identity-Aware Proxy.
