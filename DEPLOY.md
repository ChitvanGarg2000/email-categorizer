# Deploying Email Categorizer

Recommended stack: **Vercel** (frontend) + **Railway** (backend) + **OpenRouter** (LLM).

Both services have free tiers suitable for an MVP demo.

## Architecture in production

```
https://your-app.vercel.app          (Next.js frontend)
        |
        |  fetch(..., credentials: "include")
        v
https://your-api.up.railway.app      (FastAPI backend)
        |
        +--> Gmail API (OAuth)
        +--> OpenRouter API (classification)
        +--> SQLite on persistent volume (/data/app.db)
```

## Prerequisites

- GitHub repo pushed: `ChitvanGarg2000/email-categorizer`
- [OpenRouter](https://openrouter.ai/) API key
- Google Cloud project with Gmail API + OAuth client (already set up locally)

---

## Step 1 — Update Google OAuth for production

In [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials** → your OAuth client:

1. **Authorized JavaScript origins**
   - `https://your-app.vercel.app` (add after Vercel deploy; use your real URL)

2. **Authorized redirect URIs**
   - `https://YOUR-BACKEND-URL/auth/callback`
   - Example: `https://email-categorizer-api.up.railway.app/auth/callback`

Keep `http://localhost:8000/auth/callback` if you still develop locally.

---

## Step 2 — Deploy backend (Railway)

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `email-categorizer`
3. **Settings → Root Directory**: set to `backend`
4. Railway detects `Dockerfile` and `railway.toml` automatically

### Persistent database (required)

SQLite lives on disk — without a volume, data is lost on redeploy.

1. In your Railway service → **Volumes** → **Add Volume**
2. Mount path: `/data`
3. Set env var: `DATABASE_URL=sqlite:////data/app.db`

### Backend environment variables

Set these in Railway → **Variables**:

| Variable | Value |
|----------|-------|
| `GOOGLE_CLIENT_ID` | From Google Cloud |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud |
| `GOOGLE_REDIRECT_URI` | `https://YOUR-BACKEND-URL/auth/callback` |
| `FRONTEND_URL` | `https://your-app.vercel.app` |
| `SECRET_KEY` | Random string (32+ chars) |
| `LLM_PROVIDER` | `openrouter` |
| `OPENROUTER_API_KEY` | Your OpenRouter key |
| `OPENROUTER_MODEL` | `minimax/minimax-m3:free` |
| `GMAIL_SYNC_DAYS` | `14` |
| `DATABASE_URL` | `sqlite:////data/app.db` |

4. **Deploy** → copy the public URL (e.g. `https://email-categorizer-api.up.railway.app`)
5. Verify: open `https://YOUR-BACKEND-URL/health` → should return `{"status":"ok"}`

---

## Step 3 — Deploy frontend (Vercel)

### Option A — Vercel dashboard (recommended)

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → import `email-categorizer`
2. **Root Directory**: `frontend`
3. **Environment variables**:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://YOUR-BACKEND-URL` (no trailing slash) |

4. Deploy → copy your Vercel URL (e.g. `https://email-categorizer.vercel.app`)

### Option B — Vercel CLI

```bash
cd frontend
vercel
# follow prompts; set root to frontend if asked
vercel env add NEXT_PUBLIC_API_URL   # paste backend URL
vercel --prod
```

---

## Step 4 — Wire URLs together

After both are live:

1. **Google Cloud** — add production redirect URI + JS origin (Step 1)
2. **Railway** — set `FRONTEND_URL` to your Vercel URL
3. **Railway** — set `GOOGLE_REDIRECT_URI` to `https://YOUR-BACKEND-URL/auth/callback`
4. Redeploy backend if you changed env vars

---

## Step 5 — Smoke test

1. Open your Vercel URL
2. Click **Connect Gmail** → complete Google consent
3. You should land on `/dashboard`
4. Click **Sync unread** → emails should classify
5. Open **Job tracker** → job emails should appear as cards

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Login redirects then `/dashboard` shows "Not logged in" | `FRONTEND_URL` must exactly match Vercel URL (https, no trailing slash). Redeploy backend. |
| OAuth redirect mismatch | `GOOGLE_REDIRECT_URI` in Railway must exactly match Google Console redirect URI |
| CORS error in browser console | `FRONTEND_URL` on backend must match the page origin |
| Sync fails with 403 Gmail | Revoke app at [Google permissions](https://myaccount.google.com/permissions), log in again |
| Data lost after redeploy | Add Railway volume at `/data` and `DATABASE_URL=sqlite:////data/app.db` |
| LLM errors | Check `OPENROUTER_API_KEY` and model name on OpenRouter |

---

## Alternative: Render (backend)

1. [render.com](https://render.com) → **New Web Service** → connect repo
2. Root directory: `backend`
3. Runtime: **Docker**
4. Add a **Disk** mounted at `/data` (paid plan on Render; Railway free tier includes volumes)
5. Same env vars as Railway table above

---

## Local vs production env summary

**Local** (`backend/.env`):

```env
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
FRONTEND_URL=http://localhost:3000
DATABASE_URL=sqlite:///./app.db
```

**Production** (Railway):

```env
GOOGLE_REDIRECT_URI=https://your-api.up.railway.app/auth/callback
FRONTEND_URL=https://your-app.vercel.app
DATABASE_URL=sqlite:////data/app.db
```

**Frontend** (`frontend/.env.local` locally, Vercel env in prod):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000          # local
NEXT_PUBLIC_API_URL=https://your-api.up.railway.app  # prod
```
