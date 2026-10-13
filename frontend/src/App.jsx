import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import Login from './pages/Login';
import Home from './pages/Home';
import Events from './pages/Events';
import Equipment from './pages/Equipment';
import EventRequests from './pages/EventRequests';
import EventRequest from './pages/EventRequest';
import ReviewEventRequests from './pages/ReviewEventRequests';
import ReviewEventRequest from './pages/ReviewEventRequest';
import AssignEventCoordinators from './pages/AssignEventCoordinators';
import ReassignEventCoordinators from './pages/ReassignEventCoordinators';
import VenueSearch from './pages/VenueSearch';
import VenueBookings from './pages/VenueBookings';
import VenueBooking from './pages/VenueBooking';
import ReviewVenueBookings from './pages/ReviewVenueBookings';
import ReviewVenueBooking from './pages/ReviewVenueBooking';
import VenueSearchResults from './pages/VenueSearchResults';
import VenueSearchFilters from './pages/VenueSearchFilters';
import EquipmentAvailability from './pages/EquipmentAvailability';
import VenueSuitability from './pages/VenueSuitability';
import VenueSuitabilityCheck from './pages/VenueSuitabilityCheck';
import Venues from './pages/Venues';
import VenueDetails from './pages/VenueDetails';
import CreateVenue from './pages/CreateVenue';
import UpdateVenue from './pages/UpdateVenue';
import DeleteVenue from './pages/DeleteVenue';
import AppShell from './components/AppShell';

function ProtectedPage({ children }) {
  const { token, account, accountReady, canAccess } = useAuth();
  const { pathname } = useLocation();
  if (!token) return <Navigate to="/" replace />;
  if (!accountReady) return <p role="status">Loading your workspace...</p>;
  if (account.error) return <AppShell><p role="alert">{account.error}</p><button onClick={() => window.location.reload()}>Retry</button></AppShell>;
  if (pathname !== '/home' && !canAccess(pathname)) return <Navigate to="/home" replace />;
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  const { token } = useAuth();
  const protectedView = (element) => <ProtectedPage>{element}</ProtectedPage>;

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
    <Route path="/assign-event-coordinators" element={protectedView(<AssignEventCoordinators />)} />
    <Route path="/reassign-event-coordinators" element={protectedView(<ReassignEventCoordinators />)} />
    <Route path="/assign-event-requests" element={<Navigate to="/assign-event-coordinators" replace />} />
    <Route path="/coordinator-lead-dashboard" element={<Navigate to="/reassign-event-coordinators" replace />} />
    <Route path="/venue-search" element={protectedView(<VenueSearch />)} />
    <Route path="/venue-bookings" element={protectedView(<VenueBookings />)} />
    <Route path="/venue-bookings/:bookingId" element={protectedView(<VenueBooking />)} />
    <Route path="/review-venue-bookings" element={protectedView(<ReviewVenueBookings />)} />
    <Route path="/review-venue-bookings/:bookingId" element={protectedView(<ReviewVenueBooking />)} />
    <Route path="/venue-search/results" element={protectedView(<VenueSearchResults />)} />
    <Route path="/venue-search/filters" element={protectedView(<VenueSearchFilters />)} />
    <Route path="/equipment-availability" element={protectedView(<EquipmentAvailability />)} />
    <Route path="/venue-suitability" element={protectedView(<VenueSuitability />)} />
    <Route path="/venue-suitability/check/:eventId" element={protectedView(<VenueSuitabilityCheck />)} />
    <Route path="/venues" element={protectedView(<Venues />)} />
    <Route path="/venues/new" element={protectedView(<CreateVenue />)} />
    <Route path="/venues/:venueId" element={protectedView(<VenueDetails />)} />
    <Route path="/venues/:venueId/edit" element={protectedView(<UpdateVenue />)} />
    <Route path="/venues/:venueId/delete" element={protectedView(<DeleteVenue />)} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></HashRouter>;
}
