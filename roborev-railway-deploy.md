# RoboRev — Deploy to Railway

## Context

RoboRev is a full-stack app running locally in Docker Compose with three services:
- **PostgreSQL** database (14 tables, seed data with 156 units)
- **FastAPI** backend (Python, SQLAlchemy, Alembic migrations, Claude API integration)
- **React** frontend (Vite or CRA build, Tailwind, Recharts)

The code is in a private GitHub repo. I have a Railway Pro account. The goal is a live URL where an evaluator can log in with demo@example.com / demo123 and run the full platform — dashboard, diagnostics, AI chat, config templates, slideshow.

## What to Do

### Step 1: Audit the codebase for deployment readiness

Before touching Railway, check and fix these:

**Environment variables.** Every secret and config value must come from environment variables, never hardcoded. Check for:
- `ANTHROPIC_API_KEY` — Claude API key for the AI diagnosis, chat, and narrative endpoints
- `DATABASE_URL` — PostgreSQL connection string (Railway provides this automatically for its managed Postgres)
- `JWT_SECRET` — secret key for JWT token signing
- `CORS_ORIGINS` — allowed origins for the frontend (must include the Railway frontend domain)
- Any other hardcoded localhost URLs, ports, or secrets in the backend config

If any of these are hardcoded or read from a .env file without fallback to environment variables, refactor to use `os.environ.get()` with sensible defaults for local development.

**Frontend API base URL.** The React app needs to know the backend URL. This is almost certainly hardcoded to `http://localhost:8000` or similar. Refactor to use an environment variable:
- At build time: `VITE_API_URL` (if Vite) or `REACT_APP_API_URL` (if CRA)
- The default should be empty string or `/api` for local development
- Railway will set this to the backend service's public URL at build time

**CORS configuration.** Find where CORS is configured in the FastAPI app (likely `main.py` or a middleware file). Update it to:
- Read allowed origins from `CORS_ORIGINS` environment variable (comma-separated string)
- Always include `http://localhost:3000` and `http://localhost:5173` for local dev
- In production, include the Railway frontend domain

Example:
```python
origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```

**Database seed on startup.** The evaluator needs demo data when they hit the URL. Ensure the backend startup sequence:
1. Runs Alembic migrations (creates tables if they don't exist)
2. Checks if seed data exists (e.g., checks if the demo user exists)
3. If no seed data, runs the seed script (creates demo user, properties, units, comps, snapshots, default config)
4. If seed data already exists, skips seeding (idempotent)

This should happen automatically on app startup, not require a manual command. If it's currently a separate script, integrate it into the FastAPI startup event or lifespan handler.

**Health check endpoint.** Add `GET /health` to the FastAPI app if it doesn't exist:
```python
@app.get("/health")
def health():
    return {"status": "ok"}
```
Railway uses this to know when the service is ready.

### Step 2: Create Dockerfiles for each service (if not already separated)

Railway deploys individual services, not docker-compose. You need:

**Backend Dockerfile** (in the backend directory):
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Adjust the `app.main:app` path to match your actual FastAPI app location. If you use gunicorn in production, use:
```
CMD ["gunicorn", "app.main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```
Add gunicorn to requirements.txt if using this approach.

**Frontend Dockerfile** (in the frontend directory):
```dockerfile
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Frontend nginx.conf** (in the frontend directory):
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

The `try_files` fallback to index.html is critical — without it, direct navigation to any route (e.g. /properties/123) returns a 404 because nginx looks for a literal file instead of letting React Router handle it.

Adjust paths (dist vs build, package*.json vs package.json + package-lock.json) to match your actual project structure.

### Step 3: Create a railway.json (or configure via CLI)

Create `railway.json` in the project root to define the three services:

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {},
  "deploy": {}
}
```

Actually — Railway's preferred approach for multi-service is to configure via the CLI after linking the repo. The key configuration:

**Service 1: PostgreSQL**
- Add via `railway add --plugin postgresql`
- Railway auto-generates DATABASE_URL and injects it into linked services

**Service 2: Backend**
- Source: GitHub repo, root directory set to wherever the backend code lives (e.g., `/backend` or `/server`)
- Build: Dockerfile
- Environment variables set via `railway variables set`:
  - `DATABASE_URL` → auto-injected from PostgreSQL plugin
  - `ANTHROPIC_API_KEY` → I will provide this
  - `JWT_SECRET` → auto-generated via `openssl rand -hex 32`
  - `CORS_ORIGINS` → set after frontend deploys and has a domain
  - `PORT` → 8000
- Health check: `/health`
- Generate a public domain via `railway domain`

**Service 3: Frontend**
- Source: GitHub repo, root directory set to the frontend code (e.g., `/frontend` or `/client`)
- Build: Dockerfile
- Build variable set via `railway variables set`:
  - `VITE_API_URL` → the backend's public URL from the previous step
- Generate a public domain via `railway domain`

After frontend deploys, set `CORS_ORIGINS` on the backend to include the frontend's domain.

### Step 4: Deploy via Railway CLI

```bash
# Install Railway CLI if not present
npm install -g @railway/cli

# Login — THIS WILL OPEN A BROWSER. Pause here and wait for me to complete the OAuth flow.
railway login

# Link to a new project
railway init
```

After the project is created and linked, set up services and environment variables via CLI:

```bash
# Add the PostgreSQL plugin
railway add --plugin postgresql

# Set backend environment variables (select the backend service when prompted)
railway variables set ANTHROPIC_API_KEY=<I will provide this>
railway variables set JWT_SECRET=$(openssl rand -hex 32)
railway variables set PORT=8000

# After PostgreSQL is provisioned, DATABASE_URL is auto-injected — no need to set it manually.
# CORS_ORIGINS will be set after the frontend deploys and we know its domain.
```

After frontend deploys and has a public domain:
```bash
# Select the backend service, then:
railway variables set CORS_ORIGINS=https://[frontend-domain]
```

After frontend service is created, set its build arg:
```bash
# Select the frontend service, then:
railway variables set VITE_API_URL=https://[backend-domain]
```

Deploy by pushing to GitHub (Railway auto-deploys from the linked repo) or use `railway up` to deploy directly. GitHub integration is preferred — every push to main auto-deploys.

### Step 5: Post-deploy verification

After all three services are running:

1. **Hit the health check:** `curl https://[backend-domain]/health` → should return `{"status": "ok"}`

2. **Check database:** The backend logs should show Alembic migrations running and seed data being created on first startup.

3. **Check frontend:** Navigate to `https://[frontend-domain]` → should see the login page.

4. **Full evaluator walkthrough:**
   - Log in with demo@example.com / demo123
   - Dashboard loads with real API data (not hardcoded)
   - Portfolio daily burn ($911/day) is prominent
   - Click Property B → see B1 flagged as needing attention
   - Run diagnosis → progressive loading (metrics/flags first, then Claude narrative)
   - B1 scores 20-35 (CRITICAL), narrative references $91 above comps and $254/day burn
   - Open AI chat → ask "why is B1 not leasing?" → get a specific, data-grounded answer
   - Switch config template to "Value-Add Aggressive" → preview shows different flag counts
   - Switch to Property A → A1 reads as healthy
   - Check slideshow renders and keyboard navigation works

5. **Run diagnosis 3 times on Property B** — verify scoring stays within ±5 band.

6. **Check for common production issues:**
   - Mixed content warnings (HTTP resources on HTTPS page)
   - WebSocket or long-polling issues behind Railway's proxy
   - Claude API calls working (not blocked by network policy)
   - JWT auth working correctly (login, token refresh, 401 redirect)

### Step 6: Custom domain (optional)

If you have a custom domain (e.g., roborev.yourdomain.com), configure it via `railway domain` for the frontend service. Add a CNAME record pointing to Railway. Then update CORS_ORIGINS on the backend: `railway variables set CORS_ORIGINS=https://roborev.yourdomain.com`.

## Important Notes

- **Never commit secrets.** ANTHROPIC_API_KEY, JWT_SECRET, DATABASE_URL are set via `railway variables set`, not in code. They should not appear in any committed file.
- **The one manual step.** `railway login` opens a browser for OAuth — pause and wait for me to complete it. Everything else runs via CLI.
- **Railway's PORT variable.** Railway may inject its own PORT. Make sure uvicorn reads from the PORT environment variable: `--port ${PORT:-8000}`.
- **Build order matters.** Deploy PostgreSQL first, then backend (needs DATABASE_URL), then frontend (needs backend URL). Railway handles this if you set up variable references correctly.
- **Cold starts.** Railway Pro keeps services running (no sleep). Free tier sleeps after inactivity. Since you're on Pro, this isn't an issue — the evaluator won't hit a 10-second cold start.
- **Logs.** If anything fails, check Railway's deployment logs for each service. Common issues: missing environment variable, wrong Dockerfile path, port mismatch.
