# tryout

**Meeting ideas, shipped as reviewed pull requests.**

tryout reads your meeting transcripts, pulls out the ideas worth acting on, and has Gemini agents *attempt* each approved idea against your real codebase. Every attempt ends as a pull request plus a **friction log**: each blocker the agent hit (a missing credential, another team's API, a schema change, an undecided product question), who owns it, and what has to happen to unblock it. Across many attempts, those logs add up to a **bottleneck map** of your organization.

- **Live demo:** https://tryout-git-bhhkaqw34q-ww.a.run.app (sign in with Google or GitHub)
- **Demo video:** _TODO: link_
- **Demo target repo:** [hamzam1997/acme-store](https://github.com/hamzam1997/acme-store), a small fictional store with named owners and deliberately missing integrations

---

## Contents

- [The problem](#the-problem)
- [What tryout does](#what-tryout-does)
- [Try it in 3 minutes](#try-it-in-3-minutes)
- [How it works](#how-it-works)
- [Where Gemini is used](#where-gemini-is-used)
- [Architecture](#architecture)
- [Workspaces, auth and roles](#workspaces-auth-and-roles)
- [API reference](#api-reference)
- [Running locally](#running-locally)
- [Configuration](#configuration)
- [Deploying to Cloud Run](#deploying-to-cloud-run)
- [Safety, limitations and roadmap](#safety-limitations-and-roadmap)
- [Team](#team)

---

## The problem

Teams generate ideas in meetings constantly, and most never get acted on. The ones that do often run into blockers weeks into execution: a permission nobody has, a data field that doesn't exist, a dependency on another team's backlog, a decision nobody made. By then the time is already spent.

Meeting tools (Otter, Fireflies, Granola) summarize conversations and list action items. Planning tools estimate work from what people type into them. **Neither one tries the work.** So blockers are *predicted*, or discovered late, instead of *observed* early.

tryout moves that discovery to right after the meeting, while an idea is still cheap to reshape, reprioritize or drop. Engineers spend time only on ideas whose path to shipping is understood, and leaders get evidence of which teams, systems and approval steps slow the organization down.

### Example

In a weekly ops meeting, a manager suggests notifying customers automatically when a refund is delayed. tryout extracts the idea with the exact quote and timestamp, and a teammate approves it. The agent plans the change against the store's architecture, writes the code, and finds that:

1. refund status lives in the payments code, but nothing records *why* a refund is delayed (a schema change owned by `@team-payments`), and
2. sending notifications needs `notifications-service`, owned by `@team-comms`, which this repo can't reach.

It mocks the notification client, gets the tests passing, and opens a pull request. By the next meeting the team has a working partial prototype and a checklist of exactly two blockers, each with an owner.

---

## What tryout does

| Stage | Input | Output |
|---|---|---|
| **1. Onboard a repo** | A GitHub repository | An **architecture catalog**: modules, routes, models, integrations, config, owners from `CODEOWNERS`, test command |
| **2. Ingest a meeting** | A `.vtt` / `.srt` / `.txt` transcript (Meet, Zoom and Teams export these) | Minutes: summary, key points, action items |
| **3. Extract ideas** | Transcript + catalog | Catalog-grounded proposals with speaker, quote, timestamp, priority and an attempt hypothesis, deduplicated across meetings |
| **4. Approve** | One click by a person | The human gate: nothing runs without it |
| **5. Plan** | Idea + catalog + meeting evidence | A technical plan: in-repo changes kept separate from external requirements, plus a mock strategy |
| **6. Build** | Plan + isolated copy of the repo | A coding agent edits files and runs tests over up to 25 tool-calling steps, streamed live to the UI |
| **7. Log friction** | The diff + test notes | Structured blockers: category, service, owning team, mock used, required action, readiness checklist |
| **8. Publish** | Workspace changes | A pull request on `tryout/idea-<id>-attempt-<id>` with the readiness checklist in its description |
| **9. Bottleneck map** | Every friction log in the workspace | Blockers ranked by category, service and team, plus an estimate of engineering weeks saved |

---

## Try it in 3 minutes

The app has a five-step tour banner at the top of every page. Follow it:

1. **Sign in** at the [live demo](https://tryout-git-bhhkaqw34q-ww.a.run.app). **Judges: click _Continue as evaluator_**: no account needed, and every click starts a brand-new evaluator with an empty workspace, so you can run the whole flow from step 1 as many times as you like. (Google or GitHub sign-in also works; a first-time account gets a workspace pre-seeded with historical attempts.)
2. **Onboard repo:** Repositories → **Demo repository** tab → **Connect demo repository** (`hamzam1997/acme-store`), or pick one of your own repos on the **GitHub** tab and click **Onboard repository**. Gemini builds the architecture catalog in the background; open it with **View catalog** on the repository card.
3. **Ingest meeting:** Meetings → **Load demo transcript**, or upload `fixtures/meetings/2026-09-17-weekly-ops.vtt`. Minutes and ideas are extracted in the background.
4. **Approve idea:** Ideas → open a proposal (each shows who said it, the quote and the timestamp) → choose the repository → **Approve**. A live view opens and streams the agent's steps: plan, file views and edits, test runs, friction. Close it and reopen any time with **Watch live**.
5. **Run tryout → report:** when it finishes, **View report** shows the production-readiness checklist, test results, the mock adapters it wrote, the full diff, and a link to the pull request it opened.
6. **Bottleneck map:** see which categories, services and teams block ideas most, across every attempt in the workspace. Click a bar to filter the log.

---

## How it works

```mermaid
flowchart LR
    subgraph Inputs
        R[GitHub repo]
        T[Meeting transcript]
    end
    R --> O[Repo onboarder<br/>gemini-3.8-flash] --> C[(Architecture<br/>catalog)]
    T --> N[Note taker<br/>gemini-3.8-flash] --> M[(Meeting +<br/>minutes)]
    M --> X[Idea extractor<br/>gemini-3.8-flash]
    C --> X
    X --> I[(Ideas inbox)]
    I -- human approves --> P[Planner<br/>gemini-3.8-flash]
    C --> P
    P --> H[Coding agent harness<br/>gemini-3.8-flash + tools]
    H -- run_tests --> S[Sandbox runner]
    H --> F[Friction classifier<br/>gemini-3.8-flash]
    F --> L[(Friction logs)]
    H --> PR[Pull request<br/>on GitHub]
    L --> B[Bottleneck map]
    H -. live steps over SSE .-> UI[Web UI]
```

### 1. Repository onboarding: `agents/repo_onboarder.py`, `repo_scanner/`

`repo_scanner` walks the repository, classifies files (manifests, config, models, routes, integrations, entrypoints, docs) and builds a compact skeleton that fits a long-context prompt. Gemini turns it into a structured `ArchitectureCatalog` (`schemas.py`): language, framework, entrypoint, test command, modules, key files, internal models, API routes, external integrations, config keys, `CODEOWNERS` ownership and coding guidelines. The catalog is cached against the commit it was built from, and attempts refuse to run if the repository has moved on since, so ideas are always grounded in the code they will run against.

### 2. Meeting ingestion: `agents/transcript.py`, `agents/note_taker.py`

Transcripts are parsed into one normalized form (WebVTT voice spans, SRT cues or plain `Speaker: text` lines), keeping speakers and timestamps. The meeting is saved *before* any model call, so a Gemini failure costs a retry, not the upload. The note taker writes minutes: a summary, key points and action items.

### 3. Idea extraction: `agents/idea_extractor.py`

Gemini reads the transcript alongside each onboarded repository's catalog and separates real proposals from status updates and general discussion. Each idea carries its evidence (speaker, quote, cue time), a priority, the catalog touchpoints it affects, and an *attempt hypothesis*. A stable kebab-case `idea_key` deduplicates the same proposal raised again in a later meeting. Ideas land in the inbox as **Pending**: a person decides what is worth attempting.

### 4. Planning: `agents/planner.py`

On approval, the planner (gemini-3.8-flash, structured output) produces a `TechnicalPlan` that keeps two kinds of work strictly apart:

- `repo_changes`: ordered files to create or modify *inside* this repository
- `external_requirements`: every service, credential or other team's system the idea needs that this repo doesn't own, plus a `mock_strategy` for each, so the prototype and its tests run without real credentials

### 5. The coding agent: `agents/harness/`, `agents/attempt_jobs.py`

Each attempt works on a throwaway copy of the repository at the catalogued commit; files that look like secrets (`.pem`, `.key`, `credentials.json`, …) are left out of the copy. The harness runs a Gemini function-calling loop (up to 25 steps) with these tools:

| Tool | What it does |
|---|---|
| `search_code` | grep the workspace |
| `list_directory` / `view_file` | read the code (paths are confined to the workspace) |
| `edit_file` / `create_file` | change the code |
| `run_tests` | run a command in the sandbox runner (`runner/sandbox.py`): time, CPU and file-size limits, a minimal environment with no server secrets, and the whole process group killed on timeout |
| `complete_attempt` | finish with a summary, PR title and testing notes |

Every step is written to the attempt record as it happens. The UI's live view follows it over server-sent events (`/api/attempts/<id>/stream`), which read from the database so they work no matter which instance runs the attempt. An attempt that goes silent for 15 minutes (its worker died) is marked failed so it can be retried.

### 6. Friction classification: `agents/friction_classifier.py`

After the run, Gemini reviews the diff and the agent's testing notes and records each blocker as a structured `FrictionLog`:

| Category | Meaning | Est. weeks if found late |
|---|---|---|
| `EXTERNAL_SERVICE_DEPENDENCY` | Needs a service or API this repo doesn't own | 2.0 |
| `AUTH_CREDENTIAL_REQUIRED` | Needs a key, scope or access grant | 1.0 |
| `SCHEMA_MIGRATION_REQUIRED` | Needs a data model or schema change | 1.5 |
| `CROSS_TEAM_CONTRACT` | Needs another team to change or agree on an interface | 2.0 |
| `PRODUCT_DECISION` | Needs a human decision nobody has made yet | 1.0 |

Each log names the service, the owning team (from the catalog's `CODEOWNERS`), the mock that stood in for it, the action needed, and a readiness checklist with an owner per task. Classification failures never break an attempt.

### 7. Pull request: `agents/github_pr.py`

With the user's GitHub connection, tryout commits the changes to `tryout/idea-<id>-attempt-<id>` and opens a pull request against `main`. The PR description carries the agent's summary and the readiness checklist. Without a GitHub connection, the patch stays on the report page.

### 8. Bottleneck map: `views/bottlenecks.py`, `frontend/src/pages/BottlenecksPage.jsx`

All friction logs in a workspace, aggregated by category, service and owning team, with the full log below. The "engineering weeks saved" figure applies the per-category weights above. It's an estimate of what each blocker costs when found mid-sprint instead of on day 0, and the UI labels it as one.

---

## Where Gemini is used

All model calls go through Vertex AI (`llm.py`). Every stage defaults to `gemini-3.8-flash`, Google's recommended successor to the Gemini 2.5 models that retire on October 20, 2026; it is GA, fast enough for a live 25-step agent loop, and supported until at least September 2027. Each stage can be pointed at another model with its env var, for example `MODEL_CODING=gemini-4-argon`.

| Stage | Default model | Technique |
|---|---|---|
| Repo onboarding | `gemini-3.8-flash` (`MODEL_ONBOARDING`) | Long-context repo skeleton → JSON schema (`ArchitectureCatalog`) |
| Meeting minutes | `gemini-3.8-flash` (`MODEL_EXTRACTION`) | Structured output (`MeetingMinutes`) |
| Idea extraction | `gemini-3.8-flash` (`MODEL_EXTRACTION`) | Full transcript + catalog → structured candidates with evidence |
| Planning | `gemini-3.8-flash` (`MODEL_PLANNING`) | Structured output (`TechnicalPlan`) grounded in catalog + meeting |
| Coding agent | `gemini-3.8-flash` (`MODEL_CODING`) | Multi-turn function calling over 6 workspace tools |
| Friction classification | `gemini-3.8-flash` (`MODEL_PLANNING`) | Diff + testing notes → structured blockers |

---

## Architecture

| Layer | Technology | Where |
|---|---|---|
| Web UI | React 19 + Vite, URL routing, Firebase Auth client | `frontend/` |
| API | Flask 3, every route under `/api`, served by gunicorn | `app.py`, `views/` |
| Agents | Gemini via `google-genai` on Vertex AI | `agents/`, `llm.py` |
| Sandbox | Subprocess runner with resource limits | `runner/sandbox.py` |
| Data | Cloud Firestore, every document scoped to a workspace | `database/` |
| Auth | Firebase Auth (Google, GitHub), server-verified ID tokens, Flask session cookie | `views/auth.py` |
| Hosting | Cloud Run (one container serves the API and the built UI), Cloud Build deploys on push to `main` | `Dockerfile` |

Background work (minutes, idea extraction, onboarding, attempts) runs in worker threads started by the request, so the API returns immediately and the UI polls only the page you are on while that page's jobs are running.

```
├── app.py                 Flask app: blueprints, auth gate, serves frontend/dist
├── config.py              Settings from env / .env (pydantic-settings)
├── llm.py                 Shared Vertex AI client
├── schemas.py             Pydantic models: catalog, meeting, idea, plan, attempt, friction, workspace
├── agents/
│   ├── repo_onboarder.py  Architecture catalog generation
│   ├── transcript.py      .vtt / .srt / text parsing
│   ├── note_taker.py      Minutes
│   ├── idea_extractor.py  Catalog-grounded idea extraction
│   ├── planner.py         Technical plan
│   ├── harness/           Coding agent loop + tools
│   ├── attempt_jobs.py    Attempt pipeline: copy → plan → code → friction → PR
│   ├── friction_classifier.py
│   ├── github_pr.py       Branch, commit, push, open PR
│   └── git_utils.py       Clone / tarball fetch with commit pinning
├── repo_scanner/          File traversal and classification for onboarding
├── runner/sandbox.py      Limited command execution
├── database/              Firestore repositories, workspace scoping, locks, token encryption
├── views/                 HTTP API
├── seed_history.py        Demo history for new workspaces (SEED_DEMO_DATA=1)
├── demo_repo/acme_store/  Source of the fictional demo repo
├── fixtures/meetings/     Sample transcripts
├── frontend/              React app
└── tests/                 unittest suite
```

---

## Workspaces, auth and roles

- **Sign-in:** Google or GitHub through Firebase Auth. The browser sends the Firebase ID token to `/api/auth/firebase-sync`, the server verifies it with the Firebase Admin SDK and starts a session. Every other `/api` route requires that session.
- **Workspaces:** all data (repositories, meetings, ideas, attempts, friction) belongs to a workspace, and every read and write is scoped to the caller's current workspace. Each user gets a personal workspace on first sign-in and can create, rename, switch between and delete workspaces.
- **Roles:** owner, admin and member. Members read, approve, reject and run attempts. Changing what a workspace works on (repositories, meetings) and deleting ideas needs an admin or owner.
- **Invitations:** admins create invite links. Accepting one adds you to the workspace.
- **GitHub connection:** one per workspace. The token is encrypted at rest (Fernet, key derived from `SECRET_KEY`) and used for private-repo cloning and pull requests.

---

## API reference

All routes are JSON under `/api`. Everything except the auth bootstrap routes requires a signed-in session.

| Area | Routes |
|---|---|
| Auth | `GET /auth/firebase-config` · `POST /auth/firebase-sync` · `GET /auth/me` · `POST /auth/logout` · `GET /auth/github/login` · `GET /auth/github/callback` · `GET /auth/github/status` · `GET /auth/github/repos` · `POST /auth/github/logout` |
| Repositories | `GET /repositories` · `POST /repositories/onboard` · `GET /repositories/<id>` · `GET /repositories/<id>/catalog` · `DELETE /repositories/<id>` |
| Meetings | `GET /meetings` · `POST /meetings/upload` · `POST /meetings/demo` · `GET /meetings/<id>` · `POST /meetings/<id>/extract-ideas` · `DELETE /meetings/<id>` |
| Ideas | `GET /ideas?status=` · `GET /ideas/counts` · `GET /ideas/<id>` · `POST /ideas/<id>/approve` · `POST /ideas/<id>/attempts/retry` · `POST /ideas/<id>/reject` · `DELETE /ideas/<id>` |
| Attempts | `GET /attempts/<id>` (report incl. friction) · `GET /attempts/<id>/stream` (server-sent events) |
| Bottlenecks | `GET /bottlenecks` |
| Workspaces | `GET, POST /workspaces` · `PATCH, DELETE /workspaces/<id>` · `POST /workspaces/<id>/switch` · `GET /workspaces/<id>/members` · `PATCH, DELETE /workspaces/<id>/members/<uid>` · `GET, DELETE /workspaces/<id>/github` |
| Invitations | `GET, POST /workspaces/<id>/invitations` · `DELETE /workspaces/<id>/invitations/<token>` · `GET /invitations/<token>` · `POST /invitations/<token>/accept` |

`GET /health` (outside `/api`) reports liveness and whether the built UI is present.

---

## Running locally

Requirements: Python 3.12, Node 22, git, and a Google Cloud project with Vertex AI and Firestore enabled.

```bash
cp .env.example .env            # set GOOGLE_CLOUD_PROJECT, SECRET_KEY and FIREBASE_* (see Configuration)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
gcloud auth application-default login
```

Run the API and the UI in two terminals:

```bash
python app.py                   # API on http://localhost:8080
```

```bash
cd frontend && npm ci && npm run dev    # UI on http://localhost:5173, proxies /api and /health to Flask
```

Open http://localhost:5173 and sign in (`localhost` is an authorized Firebase domain). If Firestore credentials aren't available, the app falls back to an in-memory store and logs a warning, so data is lost on restart.

### Tests

```bash
SECRET_KEY=test python -m unittest discover -s tests
```

```bash
cd frontend && npm run lint && npm run build && node src/lib/route.check.mjs
```

### Production-shaped image

The Dockerfile builds the React app in a Node stage and serves it from Flask with gunicorn. On Apple Silicon, build for Cloud Run's architecture:

```bash
docker build --platform linux/amd64 -t tryout .
```

```bash
docker run --rm -p 8080:8080 --env-file .env tryout
```

---

## Configuration

Settings are read from the environment, or from `.env` locally (`config.py`).

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | (none) | Project for Vertex AI. Required for every agent stage |
| `GOOGLE_CLOUD_LOCATION` | `global` | Vertex AI location; `global` serves every current Gemini model |
| `FIRESTORE_DATABASE` | `(default)` | Firestore database id |
| `MODEL_ONBOARDING` | `gemini-3.8-flash` | Architecture catalog |
| `MODEL_EXTRACTION` | `gemini-3.8-flash` | Minutes and idea extraction |
| `MODEL_PLANNING` | `gemini-3.8-flash` | Planner and friction classifier |
| `MODEL_CODING` | `gemini-3.8-flash` | Coding agent |
| `EXECUTION_TIMEOUT_SECONDS` | `60` | Per-command limit for sandbox runs and clones |
| `SEED_DEMO_DATA` | `0` | `1` seeds demo history into each new workspace (not evaluator workspaces, which start empty) |
| `EVALUATOR_LOGIN` | `0` | `1` offers "Continue as evaluator": a new throwaway evaluator and empty workspace per click, no Google or GitHub account |
| `DEMO_GITHUB_TOKEN` | (none) | GitHub token limited to the demo repo; lets attempts by users without GitHub open real pull requests there |
| `SECRET_KEY` | (none) | Session signing and the GitHub-token encryption key. **Required**: the app refuses to start without it unless `FLASK_DEBUG=1`, which uses a random per-run key |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | (none) | GitHub OAuth app for connecting repositories |
| `GITHUB_REDIRECT_URI` | derived from request | OAuth callback override |
| `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_APP_ID` | (none) | Firebase web config served to the UI (public by design, but not committed). `FIREBASE_PROJECT_ID` falls back to `GOOGLE_CLOUD_PROJECT` |
| `PORT` | `8080` | HTTP port |
| `FLASK_DEBUG` | `0` | Debug mode; also turns off secure-only cookies for local HTTP |

Seed an existing workspace by hand with `python seed_history.py <workspace_id>`.

---

## Deploying to Cloud Run

The live service (`tryout-git`, `me-central1`) deploys continuously: a Cloud Build trigger builds the Dockerfile and rolls out a new revision on every push to `main`. Service settings that matter:

| Setting | Value | Why |
|---|---|---|
| CPU allocation | always on (`--no-cpu-throttling`) | Agent jobs run in background threads after the request returns |
| Instances | `--min-instances=1 --max-instances=3` | A warm instance for demos; attempt state and live streams live in Firestore, so they work across instances |
| `SEED_DEMO_DATA` | `1` | New workspaces open with a populated bottleneck map |
| `EVALUATOR_LOGIN` | `1` | Judges sign in with one click and always start from an empty workspace |
| `DEMO_GITHUB_TOKEN` | from Secret Manager | Evaluators' attempts on `acme-store` open real pull requests |
| Secrets | `SECRET_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` from Secret Manager | Never in the image or the repo |
| Firebase web config | `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_APP_ID` as env vars | Sign-in fails without them |
| Service account | Vertex AI User, Firestore access, Secret Manager accessor | Model calls, data and secrets |

Also add the service's `run.app` domain to Firebase Authentication → Authorized domains, and set the GitHub OAuth app's callback to `https://<service-url>/api/auth/github/callback`.

---

## Safety, limitations and roadmap

**Controls in place**

- Nothing runs without a person approving the idea, and every change lands as a pull request for human review, never on `main`.
- Each attempt works on a throwaway copy of the repo pinned to the catalogued commit; secret-looking files are excluded from the copy.
- Agent file tools can't leave the workspace. Sandbox commands get time, CPU and file-size limits and an environment with no server secrets.
- Every API route requires a verified sign-in, all data is workspace-scoped, and stored GitHub tokens are encrypted.
- Every agent step is recorded and shown on the attempt's live view and report.

**Known limitations**

- **The sandbox is not an isolation boundary.** Commands run as a subprocess on the app's own instance and network. Code from an onboarded repository's tests could reach the Cloud Run metadata server or the app's process environment. **Only onboard repositories you trust.**
- Prototypes run against mocks in a temporary workspace, not a deployed staging environment, so the agent flags what it couldn't verify instead of proving it.
- Organizational blockers (priorities, budget, compliance, another team's willingness) don't show up in code, so read the friction log alongside human judgment.
- The "weeks saved" figure uses fixed per-category weights; it's an estimate, not a measurement.
- Idea extraction makes one call per onboarded repository, and live progress is read by polling Firestore. Both are fine at team scale.

**Roadmap**

- **Isolated execution:** run each attempt's commands as an unprivileged user in their own network namespace, or as a per-attempt Cloud Run job with a zero-permission identity ([#12](https://github.com/hamzam1997/tryout/issues/12)).
- **Live preview per attempt:** deploy each attempt's branch as its own short-lived Cloud Run service so people can click through the prototype, not only read the diff ([#85](https://github.com/hamzam1997/tryout/issues/85)).
- Meeting connectors (Google Meet, Zoom, Teams) instead of uploading transcripts.
- Bottleneck trends over time and across workspaces.

---

## Team

- **Hamza Masroor** ([@hamzam1997](https://github.com/hamzam1997))
- **Aiman Hasan** ([@Aimaanhasan](https://github.com/Aimaanhasan))

Built for the AI Builder Cup (Future of Work & Enterprise Productivity).
