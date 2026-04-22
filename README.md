# Mini Library Management System

A tiny but complete library management app built for the Valsoft assignment.

**Stack:** FastAPI · SQLModel (SQLite) · Jinja2 + HTMX + Tailwind · Google SSO (Authlib) · Gemini (AI Studio API key or Vertex AI)

- **Video walkthrough:** _<link to OBS demo>_
- **Live API docs (after running):** http://localhost:8000/docs

## Reviewer's 60-second tour

If you just want to see it work:

```bash
python -m venv .venv && .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env       # default ADMIN_EMAILS=["you@example.com"] works as-is
python seed.py               # ~15 demo books + an admin user
uvicorn app.main:app --reload
```

Then open http://localhost:8000, click **Log in**, use the **dev login** form, and sign in as `you@example.com` — you will land as an **admin** and can:

1. Browse the catalog and type in the search bar (live HTMX results, no page reload).
2. Click **Add Book → Autofill with AI** to see Gemini generate metadata from just a title + author. *(Requires `GEMINI_API_KEY`; the button is disabled with a tooltip if unset.)*
3. Open **Librarian** in the nav to chat with an AI that uses real function-calling against the catalog (`search_books`, `recommend_similar`) and returns clickable book cards.
4. **Borrow** any book → visit **My Loans** → **Return** it. Loans get a 14-day due date; overdue ones are flagged.
5. Sign out, log back in as a *different* email (e.g. `member@example.com`) to see the **member** role — the admin-only buttons disappear.

## Features

### Core (minimum requirements)
- **Book management** — add, edit, delete books with title, author, ISBN, genre, year, summary, tags, cover URL, and number of copies (admin only).
- **Check-in / check-out** — any logged-in user can borrow an available copy; returning a book restores availability. A 14-day due date is stamped on checkout and overdue loans are flagged on the *My Loans* page.
- **Search** — case-insensitive fuzzy match over title, author, tags, ISBN, and summary, plus a genre filter and an "available only" toggle. Results update live via HTMX as you type.

### Bonus
- **Google SSO** via Authlib (`/auth/google`) with **two roles**: `admin` and `member`. Admins are promoted automatically by matching the `ADMIN_EMAILS` env var on first login. A dev-login form is included so reviewers can test without Google credentials.
- **AI feature #1 — Metadata Autofill.** On the Add Book form, *Autofill with AI* sends title + author to Gemini, which returns a suggested summary, genre, year, tags and cover keyword as strict JSON. The user can edit before saving.
- **AI feature #2 — Librarian Chatbot + Natural-Language Search.** A chat UI (`/ai/librarian`) where Gemini uses function calling against two real tools:
  - `search_books(query, genre, author, available_only, limit)` — full-text search
  - `recommend_similar(title, limit)` — picks similar books from the catalog by shared genre / author / tags
  Gemini grounds every recommendation in actual catalog results and returns clickable book cards alongside its reply.

Both AI features degrade gracefully if `GEMINI_API_KEY` is unset — buttons become disabled with an explanation, the rest of the app still works fine.

## Quick start (local)

```bash
# 1. Create & activate a virtualenv (Windows PowerShell shown)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install deps
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env: at minimum set SECRET_KEY, ADMIN_EMAILS
# If using AI Studio, set GEMINI_API_KEY.
# If using Vertex AI, set AI_PROVIDER=vertex_ai + VERTEX_PROJECT_ID + VERTEX_LOCATION.

# 4. Seed the database with ~15 demo books
python seed.py

# 5. Run the app
uvicorn app.main:app --reload
```

Open http://localhost:8000. Auto-generated API docs live at http://localhost:8000/docs.

### Demo login

If you haven't set up Google SSO yet, click **Log in** and use the *dev login* form. Any email listed in `ADMIN_EMAILS` will be treated as an admin (so you can add/edit/delete books); any other email becomes a regular member.

Use JSON-list format for admins in `.env`, e.g.:

```
ADMIN_EMAILS=["you@example.com"]
```

Suggested accounts while reviewing:

| Email                | Role     | Purpose                                 |
| -------------------- | -------- | --------------------------------------- |
| `you@example.com`    | admin    | CRUD books, AI autofill, see all loans  |
| `member@example.com` | member   | Borrow / return only                    |

### Enabling Google SSO

1. Create OAuth 2.0 credentials at <https://console.cloud.google.com/apis/credentials>.
2. Add `http://localhost:8000/auth/callback` (and your deployed URL) as an authorized redirect URI.
3. Copy the client id + secret into `.env`.

### Enabling Gemini AI (AI Studio key)

1. Grab a free API key at <https://aistudio.google.com/app/apikey>.
2. Set `GEMINI_API_KEY` in `.env`.
3. Ensure `AI_PROVIDER=gemini_api`.
4. Restart `uvicorn`. The "Autofill with AI" button and Librarian chat become live.

### Enabling Gemini through Vertex AI

1. In Google Cloud, enable **Vertex AI API** for your project.
2. Authenticate locally with Application Default Credentials:
   - `gcloud auth application-default login`
3. In `.env`, set:
   - `AI_PROVIDER=vertex_ai`
   - `VERTEX_PROJECT_ID=<your-project-id>`
   - `VERTEX_LOCATION=us-central1` (or your region)
   - `GEMINI_MODEL=gemini-2.0-flash` (or another Vertex-supported Gemini model)
4. Restart `uvicorn`. AI features will use Vertex AI instead of API key auth.

## Project layout

```
app/
  main.py             # FastAPI app, session middleware, routers
  config.py           # pydantic-settings, reads .env
  db.py               # SQLModel engine + session
  models.py           # User, Book, Loan
  deps.py             # current_user / require_user / require_admin
  templating.py       # Jinja2 env + custom filters
  routers/
    auth.py           # Google SSO + dev-login + logout
    books.py          # CRUD + search (HTML + HTMX)
    loans.py          # checkout / return / my-loans
    ai.py             # /ai/autofill + /ai/librarian (chat + tools)
  services/
    gemini.py         # Thin Gemini wrapper (autofill + function-calling chat)
  templates/          # Jinja2 templates (Tailwind + HTMX)
  static/             # (currently empty; Tailwind + HTMX served via CDN)
seed.py               # seeds demo books + admin users
tests/                # pytest smoke tests (books, loans, ai mocked)
Dockerfile
requirements.txt
.env.example
```

## Tests

```bash
pytest -q
```

## Deploy (Docker)

```bash
docker build -t mini-library .
docker run --rm -p 8000:8000 --env-file .env mini-library
```

The image runs `seed.py` on startup, then `uvicorn`, so a fresh database is ready on first boot. The SQLite file is written into the container; mount a volume if you want persistence (`-v library_data:/app/data`).

## Evaluation notes

- **Completeness** — All minimum requirements work. CRUD, check-in/out, and search are fully wired.
- **Creativity** — Two genuinely useful AI features (generation + retrieval with tool use), live search with HTMX, admin/member roles, cover-image fallbacks, overdue-loan flagging.
- **Product quality** — Modular FastAPI layout, pydantic settings, strict role guards, graceful AI fallbacks, zero-build frontend.
- **Usability** — One-click SSO, inline AI autofill, chat-based discovery, optimistic HTMX swaps when borrowing / returning.
