# Disposable demo frontend

## Local setup (PowerShell, from repository root)

```powershell
cd frontend/frontend
npm.cmd ci
Copy-Item .env.example .env.local
npm.cmd run dev
```

Copy the example only if `.env.local` does not already exist. It sets
`VITE_API_BASE_URL=http://127.0.0.1:8000`, the existing local backend address.
Restart Vite after changing environment configuration. On shells without the
Windows PowerShell npm-script restriction, use `npm` instead of `npm.cmd`.

## Future Render Static Site

```text
Branch: UAT
Root Directory: frontend/frontend
Build Command: npm ci && npm run build
Publish Directory: dist
```

In this Static Site's Environment settings, set `VITE_API_BASE_URL` to the future
FastAPI service's HTTPS URL before building, for example
`https://YOUR-BACKEND-SERVICE.onrender.com`. This is a placeholder, not a deployed
service. The current backend has no `/api` prefix: do not add one. Trailing
slashes are normalized; existing endpoint paths are unchanged.

The existing chain is `VITE_API_BASE_URL` -> `src/config/config.js` -> shared
Axios instance -> all services, CompanyContext, Dashboard, Done By, history and
PDF detail requests. Missing configuration throws when the application loads;
there is no default local backend in production. A successful build alone does
not prove the backend URL was configured or reachable.

Vite embeds `VITE_*` values at build time, making them visible to browsers.
Never put credentials or secrets in them. Changing the backend URL requires a
new build/redeploy. `.env` and machine-specific variants are ignored.

Set the backend service's existing `FRONTEND_ORIGIN` environment setting to the
eventual frontend HTTPS origin when deploying. This requires no backend source
change. CORS is browser policy, not authentication. Use only disposable fake data.

## SPA refresh

Under Render Static Site -> Redirects/Rewrites, add:

```text
Source: /*
Destination: /index.html
Action: Rewrite
```

Keep BrowserRouter and current routes. The rewrite serves the app for direct
navigation/refresh of `/sales-entry`, `/sales-history`, `/purchase-history`, and
`/customers`; `/sales` is not an existing application route. Render serves
existing static assets normally. No proxy or routing library change is needed.

## Verification

```powershell
node --test src/utils/*.test.mjs src/config/*.test.mjs
npm.cmd run build
```

For a cloud-configured build without a deployed backend, temporarily set
`$env:VITE_API_BASE_URL = 'https://api.example.com'` before building. Inspect
`dist/assets` to confirm this value replaced the local backend configuration.
This checks bundling, not live API connectivity. Remove the temporary shell
variable afterwards to restore local file configuration.

After actual deployment, verify direct route refresh, API requests, company
profile loading, history PDF downloads with and without letterhead. Deployment
and live cloud smoke testing are not part of this preparation task.

References: [Vite environment variables](https://vite.dev/guide/env-and-mode)
and [Render rewrites](https://render.com/docs/redirects-rewrites).
