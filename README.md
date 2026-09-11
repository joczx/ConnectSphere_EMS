# ConnectSphere EMS

ConnectSphere EMS is a role-based event planning and venue-booking system.

## Repository layout

```text
frontend/   React + TypeScript + Vite + Tailwind application
backend/    FastAPI application, API, business rules, and database access
docs/       Scrum evidence, architecture (C4), and project decisions
```

Supabase provides the managed PostgreSQL database (and may provide authentication
or storage where the team chooses to use those services). Backend schema changes
are managed with Alembic; do not store Supabase credentials in the repository.

Each area has its own README describing the intended structure and local setup
responsibilities.
