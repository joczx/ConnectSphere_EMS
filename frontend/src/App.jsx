import { useState } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import Login from './pages/Login';
import Home from './pages/Home';
import Events from './pages/Events';
import EventRequests from './pages/EventRequests';
import EventRequest from './pages/EventRequest';
import ReviewEventRequests from './pages/ReviewEventRequests';
import ReviewEventRequest from './pages/ReviewEventRequest';
import EquipmentAvailability from './pages/EquipmentAvailability';

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
    <Route path="/event-requests" element={requestsView} />
    <Route path="/event-requests/:requestId" element={requestView} />
    <Route path="/review-event-requests" element={reviewsView} />
    <Route path="/review-event-requests/:requestId" element={reviewView} />
    <Route path="/equipment-availability" element={equipmentAvailabilityView} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></HashRouter>;
}
