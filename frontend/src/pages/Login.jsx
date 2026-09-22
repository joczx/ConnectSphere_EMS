import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';

export default function Login() {
  const { signIn } = useAuth();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(response.status === 401 ? 'Unable to sign in. Incorrect email or password.' : 'Unable to sign in. Please try again.');

      const data = await response.json();

      signIn(data);

    } catch (err) { setError(err.message || 'Unable to sign in. Please try again.'); }
    finally { setBusy(false); }
  }
  return <main className="login-card panel">
    <p className="brand">ConnectSphere</p><h1>Sign in</h1><p>Access your event planning information.</p>
    <form onSubmit={submit}>
      <label>Email<input name="email" type="email" autoComplete="username" required /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
      {error && <p role="alert" className="error">{error}</p>}
      <button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>
  </main>;
}
