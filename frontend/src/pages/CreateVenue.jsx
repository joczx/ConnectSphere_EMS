import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueForm from '../components/VenueForm';
import { useAuth } from '../auth/AuthContext';
import { venuePayloadFromForm } from '../services/venueForm';

export default function CreateVenue() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState({ submitting: false, error: '', errors: {} });

  async function createVenue(event) {
    event.preventDefault();
    const payload = venuePayloadFromForm(new FormData(event.currentTarget));

    setState({ submitting: true, error: '', errors: {} });
    try {
      const result = await api('/api/venues', { method: 'POST', body: payload });
      navigate(`/venues/${result.venue.venue_id}`, { replace: true, state: { message: result.message } });
    } catch (error) {
      setState({ submitting: false, error: error.message, errors: error.details || {} });
    }
  }

  return (
    <>
      <Navbar />
      <main className="container">
        <Link to="/venues">← All venues</Link>
        <div className="heading"><div><p className="eyebrow">VENUE MANAGEMENT</p><h1>Create venue</h1></div></div>
        <p>Add a new venue and its operational characteristics to the catalogue.</p>
        <VenueForm mode="create" onSubmit={createVenue} submitting={state.submitting} error={state.error} errors={state.errors} />
      </main>
    </>
  );
}
