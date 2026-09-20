import { useState } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import Login from './pages/Login';
import Home from './pages/Home';
import Events from './pages/Events';
import Equipment from './pages/Equipment';
import EventRequests from './pages/EventRequests';
import EventRequest from './pages/EventRequest';
import ReviewEventRequests from './pages/ReviewEventRequests';
import ReviewEventRequest from './pages/ReviewEventRequest';
import VenueSearch from './pages/VenueSearch';
import VenueSearchFilters from './pages/VenueSearchFilters';
import EquipmentAvailability from './pages/EquipmentAvailability';

export default function App() {
  const [session, setSession] = useState(() => {
    try {
      const savedSession = sessionStorage.getItem('auth_session');
      if (savedSession) return JSON.parse(savedSession);
    } catch {}
    const accessToken = sessionStorage.getItem('access_token');
    return accessToken ? { access_token: accessToken } : null;
  });
  const token = session?.access_token;

  function signIn(nextSession) {
    if (nextSession?.access_token) {
      sessionStorage.setItem('auth_session', JSON.stringify(nextSession));
      sessionStorage.removeItem('access_token');
    } else {
      sessionStorage.removeItem('auth_session');
      sessionStorage.removeItem('access_token');
    }
    setSession(nextSession);
  }
  const signOut = () => signIn(null);
  async function refreshSession() {
    if (!session?.refresh_token) return null;
    const response = await fetch('/api/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    });
    if (!response.ok) return null;
    const nextSession = await response.json();
    signIn(nextSession);
    return nextSession.access_token;
  }
  const homeView = token ? <Home onSignOut={signOut} /> : <Navigate to="/" replace />;
  const eventsView = token ? <Events token={token} onSignOut={signOut} /> : <Navigate to="/" replace />;
  const requestsView = token ? <EventRequests token={token} onSignOut={signOut} /> : <Navigate to="/" replace />;
  const requestView = token ? <EventRequest token={token} onSignOut={signOut} /> : <Navigate to="/" replace />;
  const reviewsView = token ? <ReviewEventRequests token={token} onSignOut={signOut} /> : <Navigate to="/" replace />;
  const reviewView = token ? <ReviewEventRequest token={token} onSignOut={signOut} /> : <Navigate to="/" replace />;
  const equipmentAvailabilityView = token ? <EquipmentAvailability token={token} onSignOut={signOut} /> : <Navigate to="/" replace />;
  return <HashRouter><Routes>
    <Route path="/" element={token ? <Navigate to="/home" replace /> : <Login onSignIn={signIn} />} />
    <Route path="/home" element={homeView} />
    <Route path="/events" element={eventsView} />
    <Route path="/events/:eventId" element={eventsView} />
    <Route path="/equipment" element={token ? <Equipment token={token} onSignOut={signOut} /> : <Navigate to="/" replace />} />
    <Route path="/event-requests" element={requestsView} />
    <Route path="/event-requests/:requestId" element={requestView} />
    <Route path="/review-event-requests" element={reviewsView} />
    <Route path="/review-event-requests/:requestId" element={reviewView} />
    <Route path="/venue-search" element={token ? <VenueSearch token={token} onRefreshSession={refreshSession} onSignOut={signOut} /> : <Navigate to="/" replace />} />
    <Route path="/venue-search/filters" element={token ? <VenueSearchFilters onSignOut={signOut} /> : <Navigate to="/" replace />} />
    <Route path="/equipment-availability" element={equipmentAvailabilityView} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></HashRouter>;
}
