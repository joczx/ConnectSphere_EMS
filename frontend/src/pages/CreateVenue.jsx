import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueForm from '../components/VenueForm';
import { useAuth } from '../auth/AuthContext';
import { VENUE_DAYS } from '../config/venueOptions';

export default function CreateVenue() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState({ submitting: false, error: '', errors: {} });

  async function createVenue(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const operatingHours = {};
    for (const [day] of VENUE_DAYS) {
      operatingHours[day] = data.has(`${day}_closed`)
        ? { closed: true }
        : { open: data.get(`${day}_open`), close: data.get(`${day}_close`) };
    }

    const payload = {
      venue_name: data.get('venue_name'),
      capacity: Number(data.get('capacity')),
      postal_code: data.get('postal_code'),
      block_number: data.get('block_number'),
      street_name: data.get('street_name'),
      building_name: data.get('building_name') || null,
      unit_number: data.get('unit_number') || null,
      wheelchair_accessible: data.has('wheelchair_accessible'),
      blind_accessible: data.has('blind_accessible'),
      accessibility_notes: data.get('accessibility_notes') || null,
      facilities: data.getAll('facilities'),
      supported_room_layouts: data.getAll('supported_room_layouts'),
      operating_hours: operatingHours,
      default_setup_minutes: Number(data.get('default_setup_minutes')),
      default_turnaround_minutes: Number(data.get('default_turnaround_minutes')),
    };

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
