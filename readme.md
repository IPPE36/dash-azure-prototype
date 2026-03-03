Run with default `.env`:

```powershell
docker compose up --build
```

Run with local dev auth disabled:

```powershell
$env:APP_ENV_FILE=".env.dev"
docker compose up --build
```

Default dev-mode users (`AUTH_MODE=dev`) are seeded in DB on startup:

- `dev_admin` / `Admin123!`
- `dev_analyst` / `Analyst123!`
- `dev_viewer` / `Viewer123!`

Run with Entra login flow enabled:

```powershell
$env:AUTH_MODE="entra"
docker compose up --build
```

Before `entra`, set Azure app redirect URI to:

`http://localhost:8050/getAToken`


# Environment target: local | azure | databricks
# Auth mode: dev | entra
# console | json
