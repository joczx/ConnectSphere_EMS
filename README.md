# ConnectSphere EMS

ConnectSphere EMS is a web-based event planning and venue booking system designed to help teams manage events, venue availability, and booking activity in one place.

The project is split into a frontend app, a Python Flask backend, and a Supabase-backed PostgreSQL database. This keeps the project organised, easy to understand, and simple to extend for a student team.

## Tech stack

- Frontend: React, JavaScript, Tailwind CSS
- Backend: Python, Flask
- Database: Supabase (PostgreSQL)
- Environment management: .env files

## Project overview

ConnectSphere allows users to:

- view upcoming events
- browse available venues
- manage bookings and event details
- connect the frontend to backend APIs
- store and retrieve structured data using Supabase


## Project structure


## Frontend setup

The frontend lives in the `frontend/` folder and uses React + Vite + Tailwind CSS.

### Prerequisites

- Node.js and npm installed
- Basic understanding of React and JavaScript

### Install dependencies

```bash
cd frontend
npm install
```

### Start the frontend

```bash
npm run dev
```

This usually runs on:

```text
http://localhost:5173
```

## Flask backend setup

The backend lives in the `backend/` folder and is built using Python + Flask.

### Prerequisites

- Python 3.10 or later
- pip installed

### Create and activate a virtual environment (optional)

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### Install backend dependencies

```bash
pip install -r requirements.txt
```

### Start the Flask backend

```bash
python run.py
```

Or:

```bash
flask run
```

The backend usually runs on:

```text
http://localhost:5000
```

## Required dependencies

### Frontend dependencies

Common packages usually include:

- react
- react-dom
- vite
- tailwindcss
- postcss
- autoprefixer

### Backend dependencies

Typical Flask backend packages include:

- Flask
- Flask-CORS
- python-dotenv

Use the project’s actual dependency files in the repo to install the correct versions.

## How the app communicates

The system is structured as follows:

1. The React frontend sends requests to the Flask backend using HTTP.
2. The Flask backend receives the request and handles the logic.
3. The backend connects to Supabase/PostgreSQL using the configured database URL.
4. The database returns the required data.
5. The backend sends JSON back to the frontend.
6. The frontend renders the data in pages and components.

This keeps the system modular and easy to maintain.

## Supabase and database connection

Supabase is used as the managed PostgreSQL database for the project.

In practice, the Flask backend reads the database connection settings from environment variables and uses them to connect to the Supabase instance.

Typical connection flow:

- create a Supabase project
- retrieve the PostgreSQL connection string and keys from the dashboard
- store them in backend `.env`
- let Flask connect to Supabase when the app runs

This approach keeps credentials out of the repository and allows each developer to use their own local environment variables.

## Recommended workflow

1. Start Supabase and set up your project database.
2. Configure `.env` files for both frontend and backend.
3. Run the backend.
4. Run the frontend.
5. Test the API connection and confirm data flows correctly.

## Summary

This project follows a standard three-layer architecture:

- Frontend: React + Tailwind UI
- Backend: Python + Flask API
- Database: Supabase PostgreSQL

It is designed to be clear, simple, and beginner-friendly while still being suitable for a growing event management application.

