import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import Login from './pages/Login';
import Home from './pages/Home';
import Events from './pages/Events';
import Equipment from './pages/Equipment';
import EventRequests from './pages/EventRequests';
import EventRequest from './pages/EventRequest';
import ReviewEventRequests from './pages/ReviewEventRequests';
import ReviewEventRequest from './pages/ReviewEventRequest';
import VenueSearch from './pages/VenueSearch';
import VenueSearchResults from './pages/VenueSearchResults';
import VenueSearchFilters from './pages/VenueSearchFilters';
import EquipmentAvailability from './pages/EquipmentAvailability';
import VenueSuitability from './pages/VenueSuitability';
import VenueSuitabilityCheck from './pages/VenueSuitabilityCheck';

export default function App() {
  const { token } = useAuth();
  const protectedView = (element) => token ? element : <Navigate to="/" replace />;

  return <HashRouter><Routes>
    <Route path="/" element={token ? <Navigate to="/home" replace /> : <Login />} />
    <Route path="/home" element={protectedView(<Home />)} />
    <Route path="/events" element={protectedView(<Events />)} />
    <Route path="/events/:eventId" element={protectedView(<Events />)} />
    <Route path="/equipment" element={protectedView(<Equipment />)} />
    <Route path="/event-requests" element={protectedView(<EventRequests />)} />
    <Route path="/event-requests/:requestId" element={protectedView(<EventRequest />)} />
    <Route path="/review-event-requests" element={protectedView(<ReviewEventRequests />)} />
    <Route path="/review-event-requests/:requestId" element={protectedView(<ReviewEventRequest />)} />
    <Route path="/venue-search" element={protectedView(<VenueSearch />)} />
    <Route path="/venue-search/results" element={protectedView(<VenueSearchResults />)} />
    <Route path="/venue-search/filters" element={protectedView(<VenueSearchFilters />)} />
    <Route path="/equipment-availability" element={protectedView(<EquipmentAvailability />)} />
    <Route path="/venue-suitability" element={protectedView(<VenueSuitability />)} />
    <Route path="/venue-suitability/check/:eventId" element={protectedView(<VenueSuitabilityCheck />)} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></HashRouter>;
}
