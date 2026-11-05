# ConnectSphere EMS

ConnectSphere EMS is a web-based event management system. Event Organisers submit event requests, Event Coordinator Lead assign coordinators to an event, Event Coordinators review and plan them, Venue Staff approve venue bookings, Technical Support Staff manage equipment reservations, Safety Officer checks event for safety, and Attendees register for confirmed events.

**Git repository:** https://github.com/joczx/ConnectSphere_EMS

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, React Router |
| Backend | Python 3.13, Flask |
| Database and authentication | Supabase (PostgreSQL) |
| Tests | pytest / unittest (backend), Playwright (browser end-to-end) |
| CI/CD | GitHub Actions |

## Project structure

```text
ConnectSphere_EMS/
├── backend/                  Flask API
│   ├── app/
│   │   ├── routes/           HTTP endpoints (thin: parse, call a service, respond)
│   │   ├── schemas/          Input validation, no Flask or Supabase imports
│   │   └── services/         Business logic and Supabase access
│   ├── tests/                Unit tests (no database needed)
│   │   └── integration/      Integration tests against a Supabase test project
│   ├── run.py                Entry point
│   ├── requirements.txt
│   ├── ruff.toml             Lint rules used by CI
│   └── .env.example          Template for backend/.env
├── frontend/                 React application
│   ├── src/                  Pages, components, auth context, services
│   ├── e2e/                  Playwright end-to-end tests
│   └── playwright.config.js
├── supabase/                 SQL migrations, numbered in the order they apply
├── docs/                     Feature and test documentation
├── smoke.sh                  Smoke test run against the release package
└── .github/workflows/tests.yml   CI pipeline
```

## Prerequisites

- Python 3.13 (3.10 or later works locally)
- Node.js 22 and npm
- The environment files folder provided with the submission (see step 1)

## 1. Configure environment variables

Secrets are never committed to the repository. They are supplied separately in the **environment files folder provided with the submission**, which contains two ready-filled files:

| File | Used by |
|---|---|
| `.env` | Running the backend (steps 2 and 3) |
| `.env.integration-test` | Integration and end-to-end tests |

Copy both files into the `backend/` folder of the project.

```bash
# macOS/Linux
cp 7/.env backend/.env
cp 7/.env.integration-test backend/.env.integration-test
```

```powershell
# Windows PowerShell
Copy-Item 7\.env backend\.env
Copy-Item 7\.env.integration-test backend\.env.integration-test
```

Both file names start with a dot, so they may be hidden. On Windows, turn on **View → Show → Hidden items** in File Explorer; on macOS, press **Cmd + Shift + .** in Finder.

After copying, `backend/` should contain `.env`, `.env.integration-test` and `.env.example`. No values need to be edited.

The frontend needs no `.env`: it signs in and fetches data through the backend, which Vite proxies on `/api`.

<details>
<summary>Using your own Supabase project instead</summary>

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Where to find it |
|---|---|
| `SUPABASE_URL` | Supabase dashboard → Project Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Supabase dashboard → Project Settings → API → anon / publishable key |

Apply the migrations in `supabase/` in numeric order first.

</details>

## 2. Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

The API runs at http://localhost:5000. Opening that URL returns `{"message": "ConnectSphere Flask API is running!"}`.

## 3. Run the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with a Supabase user account. Requests to `/api` are forwarded to the backend on port 5000, so the backend must be running.

## Running the tests

### Unit tests

Supabase is mocked, so no database or credentials are needed.

```bash
cd backend
python -m pytest tests --ignore=tests/integration
```

### Integration tests

These call the real API against a **separate** Supabase test project, never the development one; the test setup refuses to run if both point at the same project. They read `backend/.env.integration-test`, copied from the provided folder in step 1. Its test accounts already exist, so no setup is needed:

```bash
cd backend
RUN_INTEGRATION_TESTS=1 python -m pytest tests/integration -v
```

On Windows PowerShell, set the variable first: `$env:RUN_INTEGRATION_TESTS="1"; python -m pytest tests/integration -v`

### End-to-end (browser) tests

These use the same `backend/.env.integration-test`. Playwright starts the backend and frontend itself.

```bash
cd frontend
npx playwright install chromium   # once
npx playwright test
npx playwright show-report        # optional: open the HTML report
```

### Lint

```bash
python -m pip install ruff
ruff check backend
```

## CI pipeline (continuous delivery)

The pipeline in [.github/workflows/tests.yml](.github/workflows/tests.yml) runs on every pull request and on every push to `main`. It builds the release package once, checks that package on its own, and then holds the release for human approval.

| Job | What it does | Runs on |
|---|---|---|
| `lint` | Ruff static checks on the backend | every PR and push |
| `test-cases-ci` | Backend unit tests | every PR and push |
| `integration-tests` | Backend integration tests against the Supabase test project | every PR and push |
| `e2e-tests` | Playwright browser tests of key user journeys | every PR and push |
| `audit` | `pip-audit` and `npm audit` for dependencies with known vulnerabilities | every PR and push |
| `package` | Builds `connectsphere-release.zip` (backend with its dependencies, built frontend, migrations) exactly once, and records an SBOM | every PR and push |
| `smoke` | Unzips the package, runs it (not the source), and probes the API and the built frontend with `smoke.sh` | every PR and push |
| `staging` | Placeholder release step for the staging environment | push to `main` only |
| `production` | Waits for a named reviewer to approve, then marks the release as approved | push to `main` only |

The integration and end-to-end jobs need the repository secret `INTEGRATION_ENV_FILE`, which holds the contents of `backend/.env.integration-test`.

The project is not deployed anywhere, so `staging` and `production` only record the release. The `production` environment has required reviewers, so every green build stops at **Waiting for review** until a team member has looked at the evidence (the checks, the smoke test and the SBOM) and approves it. That approval is what makes this continuous delivery rather than continuous deployment.

The release package and its SBOM can be downloaded from the **Artifacts** section of any pipeline run in the Actions tab.

## Further documentation

Feature and testing notes are in [docs/](docs/). [agents.md](agents.md) maps each implemented user story to the files that implement it.
