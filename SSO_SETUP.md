# Google SSO Setup — L'Oréal observability dashboard

The app supports two sign-in paths:

1. **Google Sign-In (SSO)** — restricted to `@loreal.com` accounts by default.
2. **Username / password** (`admin1` / `pwd1`) — kept as a fallback for admins/CI.

Both paths issue the same in-app JWT (24-hour TTL).

---

## One-time setup: create an OAuth Web Client in GCP

```bash
# 1. Enable the Identity Services API (free, no quota)
gcloud services enable iap.googleapis.com --project=oa-apmena-observability-dv

# 2. Configure the OAuth consent screen (do this once in the Console UI)
#    https://console.cloud.google.com/apis/credentials/consent?project=oa-apmena-observability-dv
#    - User type: Internal (everyone in your Workspace)
#    - App name:  GenAI Observability
#    - Support email: <you>@loreal.com
#    - Authorized domain: loreal.com
#    - Save

# 3. Create the OAuth 2.0 Web Client
#    https://console.cloud.google.com/apis/credentials?project=oa-apmena-observability-dv
#    → CREATE CREDENTIALS → OAuth client ID
#    Application type: Web application
#    Name: otel-dashboard
#    Authorized JavaScript origins: add every URL the app is served from:
#      - https://otel-dashboard-786386076156.us-central1.run.app   (Cloud Run)
#      - http://localhost:7860                                     (local docker test)
#      - http://localhost:3000                                     (vite dev server)
#      - https://<your-preview-url>.preview.emergentagent.com      (preview env, if used)
#    Authorized redirect URIs: leave empty (we use the GIS implicit-credential flow, no redirect)
#    → Create → copy the Client ID (looks like 12345-abc.apps.googleusercontent.com)
```

## Wire it into the app

Edit **`/app/.env`** and paste the Client ID:

```bash
GOOGLE_CLIENT_ID=12345-abc.apps.googleusercontent.com
ALLOWED_DOMAIN=loreal.com
```

Then either:

- **Local dev:** `sudo supervisorctl restart backend` (frontend auto-picks up).
- **Cloud Run:** rebuild + deploy. The `.env` is copied into the image; the SSO button appears automatically.

```bash
gcloud builds submit --tag gcr.io/oa-apmena-techsandbox-ap-dv/otel-dashboard
gcloud run deploy otel-dashboard \
  --image gcr.io/oa-apmena-techsandbox-ap-dv/otel-dashboard \
  --region us-central1 \
  --service-account dashboard-readonly@oa-apmena-observability-dv.iam.gserviceaccount.com \
  --set-env-vars APP_ENV=cloud,GCP_PROJECT=oa-apmena-observability-dv,BQ_DATASET=cds_otel \
  --allow-unauthenticated
```

## How the auth flow works

| Step | Component | What happens |
|---|---|---|
| 1 | Frontend | On load, `GET /api/config` returns `{google_client_id, allowed_domain}`. |
| 2 | Frontend | If `google_client_id` is set, the page wraps itself in `<GoogleOAuthProvider>` and renders `<GoogleLogin hosted_domain="loreal.com">`. |
| 3 | User | Clicks **Sign in with Google** → GIS popup (FedCM-capable) → picks their L'Oréal account. |
| 4 | Browser | GIS hands back a JWT *ID token* (`credential`) to our SPA. |
| 5 | Frontend | `POST /api/login/google { credential }`. |
| 6 | Backend | `google.oauth2.id_token.verify_oauth2_token` verifies the signature & `aud` against `GOOGLE_CLIENT_ID`, then checks `hd == "loreal.com"` (or email suffix). |
| 7 | Backend | Issues an HS256 JWT (sub = user email, exp = 12h) → returned to SPA. |
| 8 | Frontend | Stores the token in `localStorage.token`; axios interceptor adds `Authorization: Bearer ...` to all `/api/*` calls. |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Google button doesn't show up | `/api/config` returns empty `google_client_id` | Set `GOOGLE_CLIENT_ID` in `.env` and restart |
| "Error 400: redirect_uri_mismatch" | Browser origin not on the allowlist | Add the exact origin (incl. scheme + port) to Authorized JavaScript origins in the Console |
| "invalid Google token" (401) | Client ID mismatch — frontend & backend disagree | Confirm `GOOGLE_CLIENT_ID` in `.env` is the *same* value used by the frontend (it always reads from `/api/config`, so they can't drift unless you edit) |
| "only loreal.com accounts allowed" (403) | A non-`@loreal.com` user tried to sign in | Expected. Set `ALLOWED_DOMAIN=` (empty) in `.env` to allow any Google account. |
| Sign-in works but every `/api/*` call returns 401 | Token expired (12h) or JWT_SECRET changed | User just signs in again. To bump TTL, set `JWT_TTL_HOURS=24` in `.env`. |

## Security notes

- The OAuth Client *Secret* is **not** used or needed (this is the implicit ID-token flow). Don't paste any secret into the .env.
- The HS256 signing secret defaults to a dev value. **Set `JWT_SECRET` to a strong random string in production**, e.g. `JWT_SECRET=$(openssl rand -hex 32)`.
- The username/password fallback is still active. To disable it in production, set `ADMIN_USER` and `ADMIN_PASS` to long random strings (or remove the `/api/login` route entirely).
