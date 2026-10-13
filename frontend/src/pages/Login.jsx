import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';

export default function Login() {
  const { signIn } = useAuth();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.currentTarget));
    body.email = body.email.trim();
    if (!body.email || !body.password) {
      setError('Email and password are required.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!response.ok) {
        setError(response.status === 401
          ? 'Incorrect email or password. Please try again.'
          : 'Unable to sign in right now. Please try again.');
        return;
      }

      const data = await response.json();

      signIn(data);

    } catch {
      setError('Unable to sign in right now. Please try again.');
    }
    finally { setBusy(false); }
  }
  return <div className="login-page"><div className="login-heading"><p>ConnectSphere</p><h1>Event Management System</h1><span>Your workspace for seamless event planning</span></div><main className="login-card panel">
    <h2>Welcome back</h2><p>Sign in to your account to continue.</p>
    <form onSubmit={submit} noValidate>
      <label>Email<input name="email" type="email" autoComplete="username" required /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
      {error && <p role="alert" className="error">{error}</p>}
      <button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>
  </main></div>;
}
