# Cloud Build trigger — branch `feature/newUI` → Cloud Run

This repo ships a `cloudbuild.yaml` that builds the image and deploys to Cloud
Run in one go. **No `.env` file is baked into the image.** All runtime
configuration is set via env vars on the Cloud Run service.

## 1 · Connect the GitHub repo (one time, if not already done)

Console → **Cloud Build → Repositories** → **Link repository** →
authenticate → pick `LuC-9/observability-dashboard` (or your fork).

## 2 · Create the trigger

Console → **Cloud Build → Triggers → CREATE TRIGGER**

| Field | Value |
|---|---|
| Name | `otel-dashboard-newui` |
| Region | `us-central1` (or your preferred region) |
| Event | **Push to a branch** |
| Source repo | the repo you linked in step 1 |
| Branch regex | `^feature/newUI$` |
| Configuration | **Cloud Build configuration file (yaml or json)** |
| Cloud Build config file location | `cloudbuild.yaml` |

## 3 · Configure substitution variables (THIS is your "env file")

Same screen, scroll down to **Substitution variables → ADD VARIABLE**.
Add these — they override the defaults at the bottom of `cloudbuild.yaml`:

| Variable | Value | Sensitive? |
|---|---|---|
| `_REGION` | `us-central1` | no |
| `_SERVICE` | `otel-dashboard` | no |
| `_IMAGE` | `gcr.io/oa-apmena-techsandbox-ap-dv/otel-dashboard` | no |
| `_APP_ENV` | `cloud` | no |
| `_GCP_PROJECT` | `oa-apmena-observability-dv` | no |
| `_BQ_DATASET` | `cds_otel` | no |
| `_GOOGLE_CLIENT_ID` | `15226554049-…apps.googleusercontent.com` | no (client IDs are public by design) |
| `_ALLOWED_DOMAIN` | `loreal.com` | no |
| `_SERVICE_ACCOUNT` | `dashboard-readonly@oa-apmena-observability-dv.iam.gserviceaccount.com` | no |

⚠️ **Never put `_JWT_SECRET` or `_ADMIN_PASS` here as plain substitution variables** —
they'd be visible to anyone with `roles/cloudbuild.builds.viewer`. Use Secret Manager
instead (next step).

## 4 · Move secrets to Secret Manager (recommended)

```bash
# JWT signing secret — generate a fresh random one
echo -n "$(openssl rand -hex 32)" \
  | gcloud secrets create jwt-secret \
      --project=oa-apmena-techsandbox-ap-dv \
      --replication-policy=automatic --data-file=-

# Optional: a strong admin password if you keep the user/pass fallback
echo -n "$(openssl rand -base64 24)" \
  | gcloud secrets create admin-pass \
      --project=oa-apmena-techsandbox-ap-dv \
      --replication-policy=automatic --data-file=-

# Allow the Cloud Run runtime SA to read them
for s in jwt-secret admin-pass; do
  gcloud secrets add-iam-policy-binding $s \
    --project=oa-apmena-techsandbox-ap-dv \
    --member="serviceAccount:dashboard-readonly@oa-apmena-observability-dv.iam.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor
done
```

Then uncomment the `--set-secrets=…` line in `cloudbuild.yaml` so the deploy
step wires them into the running container as env vars.

## 5 · Permissions checklist

The **Cloud Build service account** (`<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com`)
needs these roles on `oa-apmena-techsandbox-ap-dv`:

```bash
PROJECT=oa-apmena-techsandbox-ap-dv
CB_SA=$(gcloud projects describe $PROJECT --format='value(projectNumber)')@cloudbuild.gserviceaccount.com

for role in roles/run.admin roles/iam.serviceAccountUser roles/storage.admin; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:$CB_SA" --role=$role
done
```

Also, the **runtime service account** (`dashboard-readonly@…`) needs:

| Role | Where |
|---|---|
| `roles/bigquery.dataViewer` | `cds_otel` dataset on `oa-apmena-observability-dv` |
| `roles/bigquery.jobUser` | `oa-apmena-observability-dv` (project-level) |
| `roles/secretmanager.secretAccessor` | each secret you created in step 4 |

## 6 · Add the deployed URL as an OAuth origin

After the first successful deploy, Cloud Run will tell you the URL, e.g.
`https://otel-dashboard-abc123-uc.a.run.app`. Add it to **Authorized
JavaScript origins** on the OAuth client (`15226554049-…`) or your Google
sign-in will fail with `origin not allowed`.

## 7 · Push to the branch

```bash
git checkout -b feature/newUI
git add .
git commit -m "deploy: trigger Cloud Build"
git push origin feature/newUI
```

Watch the build at **Cloud Build → History**. Should take 4–6 minutes the
first time, 90s on subsequent builds (Docker layer cache). After the deploy
step succeeds, hit the Cloud Run URL — you should land on the login page
with the Google button.

## Day-to-day: changing a value

| What changed | What to do |
|---|---|
| Trivial config (e.g. swap `_ALLOWED_DOMAIN`) | Edit the substitution variable on the trigger → push any commit to retrigger |
| Secret value (e.g. new JWT secret) | `gcloud secrets versions add jwt-secret --data-file=…` → push any commit |
| Code | Just push to `feature/newUI` |
| Need to roll back | Cloud Run console → Revisions tab → click previous green check → **MANAGE TRAFFIC → 100%** |

That's it. From here on, every push to `feature/newUI` ships a fresh build.
