# Backend

This directory will contain the Python + FastAPI service. It owns API validation,
authorisation, event workflow rules, conflict detection, and persistence through
SQLAlchemy.

## Intended layout

| Directory | Responsibility |
| --- | --- |
| `app/main.py` | FastAPI application entry point and router registration. |
| `app/routers/` | HTTP endpoints. Keep these thin; call a service for business work. |
| `app/database.py` | SQLAlchemy engine, session, and Supabase PostgreSQL configuration. |
| `app/models/` | SQLAlchemy persistence models. |
| `app/schemas/` | Pydantic request and response schemas. |
| `app/services/` | Visible domain workflows and business rules. |
| `tests/` | Unit and integration tests. |
| `alembic/versions/` | Alembic database migrations. |

## Supabase

Supabase is the managed PostgreSQL provider. Configure a server-only
`DATABASE_URL` for SQLAlchemy/Alembic and, if needed, Supabase project variables
such as `SUPABASE_URL` and a server-side key in an uncommitted `.env` file.

Never expose a Supabase service-role key to the frontend. Apply schema changes
through reviewed Alembic migrations, rather than manually changing production
tables in the Supabase dashboard.

Add more layers only when the project genuinely needs them. For example,
authorisation helpers can start beside the relevant router or service, and
database queries can stay with the relevant service until duplication makes a
separate repository useful.
