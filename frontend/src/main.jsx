// Vite application entry point (to be implemented).
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.js';
import './index.css';

const rootElement = document.getElementById('root');
// const clientID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const clientID = '703147905350-nanl3h1u0ravqj0k2pfraqsjlqm3pa3c.apps.googleusercontent.com';

if (!rootElement) {
  throw new Error('Root element was not found');
}
