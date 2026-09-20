import { useState } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import Login from './pages/Login';
import Home from './pages/Home';
import Events from './pages/Events';
import Equipment from './pages/Equipment';

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem('access_token'));
  function signIn(value) {
    if (value) sessionStorage.setItem('access_token', value);
    else sessionStorage.removeItem('access_token');
    setToken(value);
  }
  const signOut = () => signIn(null);
  const homeView = token ? <Home onSignOut={signOut} /> : <Navigate to="/" replace />;
  const eventsView = token ? <Events token={token} onSignOut={signOut} /> : <Navigate to="/" replace />;
  return <HashRouter><Routes>
    <Route path="/" element={token ? <Navigate to="/home" replace /> : <Login onSignIn={signIn} />} />
    <Route path="/home" element={homeView} />
    <Route path="/events" element={eventsView} />
    <Route path="/events/:eventId" element={eventsView} />
    <Route path="/equipment" element={token ? <Equipment token={token} onSignOut={signOut} /> : <Navigate to="/" replace />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></HashRouter>;
}
