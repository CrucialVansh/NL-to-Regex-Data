# NL Transform Frontend

React + Vite UI for the NL-to-regex data processing platform.

## Features

- CSV / XLSX upload with column detection
- Natural-language transform (regex or literal replace)
- Live job progress polling and cancellation
- Paginated results table
- Upload / job history sidebar

## Docker (production build)

Built and served automatically by the root `docker-compose.yml`:

```bash
# From repo root
docker compose up --build frontend
```

Open http://localhost:3000 — nginx proxies `/api` and `/llm` to the Django backend.

## Local development

```bash
npm ci
npm run dev
```

Open http://localhost:5173. Vite dev server proxies API calls to `http://127.0.0.1:8000` (see `vite.config.js`).

Requires the backend running on port 8000 with Celery worker active for transforms.

### Environment

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `''` (same origin) | API base URL for production builds |

Leave empty when using Docker nginx or Vite dev proxy. Set to `http://localhost:8000` only if serving the built `dist/` without a reverse proxy.

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Preview production build |
| `npm run lint` | ESLint |

## API contract

All paths are relative to the API base. See `src/api/` and `backend/README.md` for endpoint details.
