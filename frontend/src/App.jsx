import { useState } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import Login from './pages/Login';
import Events from './pages/Events';

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('access_token'));
  function signIn(value) {
    if (value) sessionStorage.setItem('access_token', value);
    else sessionStorage.removeItem('access_token');
    setToken(value);
  }
  const view = token ? <Events token={token} onSignOut={() => signIn(null)} /> : <Navigate to="/" replace />;
  return <HashRouter><Routes>
    <Route path="/" element={token ? <Navigate to="/events" replace /> : <Login onSignIn={signIn} />} />
    <Route path="/home" element={<Navigate to="/events" replace />} />
    <Route path="/events" element={view} />
    <Route path="/events/:eventId" element={view} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></HashRouter>;
}
