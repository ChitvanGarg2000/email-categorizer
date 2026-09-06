# Inbox Categorizer — MVP

Connects to Gmail via OAuth2, pulls unread messages, and classifies each into
one of: Job/Interview, Bills/Payments, Personal, Newsletter/Promotions, Other.

Classification is hybrid: fast regex/sender rules catch obvious cases for
free; anything ambiguous falls back to a local Ollama LLM call. Already-classified
messages are cached by Gmail message ID so re-syncing doesn't re-spend LLM
calls on the same email.

## Architecture

```
frontend (Next.js)  --cookie session-->  backend (FastAPI)  --> Gmail API
                                                |
                                                +--> SQLite (users, tokens, classified emails)
                                                +--> Ollama (local LLM fallback classification)
```

## Setup

### 1. Google Cloud (OAuth + Gmail API)

1. Create a project at console.cloud.google.com
2. Enable the **Gmail API** (APIs & Services > Library)
3. Configure the **OAuth consent screen** (External, testing mode is fine for
   an MVP — this lets up to 100 manually-added test users log in without
   needing Google's full verification review). Under **Data Access**, add the
   scope `https://www.googleapis.com/auth/gmail.readonly` (Gmail API > read
   mail) — without this, Google will only return email/openid scopes and
   login will fail.
4. Create an **OAuth Client ID** (Web application):
   - Authorized redirect URI: `http://localhost:8000/auth/callback`
5. Add yourself (and anyone else demoing it) as a test user under the consent
   screen's "Test users" section — required while unverified

### 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY
# install Ollama (ollama.com) and pull the model: ollama pull llama3.2:3b
uvicorn app.main:app --reload
```

Backend runs at http://localhost:8000. Visit `/health` to confirm it's up.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Frontend runs at http://localhost:3000. Click "Connect Gmail" to start the
OAuth flow.

## Known MVP limitations (intentional scope cuts)

- **Categories are fixed**, not user-customizable — customization is the
  natural v2 feature.
- **Tokens stored in plaintext** in SQLite. Fine for a local demo; a real
  deployment needs field-level encryption on `access_token`/`refresh_token`.
- **No real-time sync** — sync is a manual button (polling model), not Gmail
  Pub/Sub push notifications. Simpler to run and demo; real-time is a
  reasonable v2 addition.
- **Session store is an in-process signed cookie** — fine for one backend
  instance; a multi-instance deploy would move this to Redis.
- **Not Google-verified** — works for you and manually-added test users
  (up to 100) without needing to go through Google's CASA security
  assessment, which is the right trade-off for a portfolio piece.

## What to point to in an interview

- OAuth2 authorization-code flow end-to-end, including refresh token handling
- Hybrid classification pipeline (rules first, LLM fallback) and why —
  cost/latency vs. accuracy trade-off
- Idempotent sync (dedup by `gmail_message_id`) so re-syncing is cheap
- Clear separation of concerns: `gmail_service.py` (external API),
  `classifier.py` (business logic), routers (HTTP layer)
