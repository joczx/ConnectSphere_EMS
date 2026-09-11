# Frontend

This directory will contain the React + TypeScript + Vite + Tailwind CSS client.

## Intended source layout

| Directory | Responsibility |
| --- | --- |
| `src/main.tsx` | Vite application entry point. |
| `src/App.tsx` | Top-level application component. |
| `src/router.tsx` | Central route definitions and role-aware route guards. |
| `src/pages/` | Route-level screens for each user journey. |
| `src/components/` | Reusable UI components, including shared navigation. |
| `src/services/` | Typed calls to the FastAPI backend. |
| `src/types/` | Shared frontend domain and API types. |
| `src/styles/` | Global CSS and Tailwind entry styles. |
| `src/assets/` | Static images and other bundled assets. |

Keep business rules, availability checks, authorisation enforcement, and booking
conflict decisions on the backend. The frontend should render the appropriate UI
for the signed-in role and consume the backend API.
