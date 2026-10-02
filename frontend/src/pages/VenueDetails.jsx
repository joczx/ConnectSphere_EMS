import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';
import { VENUE_DAYS, VENUE_FACILITIES, VENUE_ROOM_LAYOUTS } from '../config/venueOptions';

const LABELS = new Map([...VENUE_FACILITIES, ...VENUE_ROOM_LAYOUTS]);

function labels(values) {
  return values?.length ? values.map(value => LABELS.get(value) || value.replaceAll('_', ' ')).join(', ') : 'None specified';
}

function address(venue) {
  return [venue.unit_number, venue.building_name, `${venue.block_number} ${venue.street_name}`, venue.postal_code].filter(Boolean).join(', ');
}

function hours(operatingHours) {
  return VENUE_DAYS.map(([key, label]) => {
    const schedule = operatingHours?.[key];
    return `${label}: ${schedule?.closed ? 'Closed' : schedule?.open && schedule?.close ? `${schedule.open}–${schedule.close}` : 'Not specified'}`;
  }).join('\n');
}

export default function VenueDetails() {
  const { venueId } = useParams();
  const { api } = useAuth();
  const location = useLocation();
  const [state, setState] = useState({ loading: true, venue: null, error: '' });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, venue: null, error: '' });
    api(`/api/venues/${encodeURIComponent(venueId)}`, { cache: 'no-store', signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setState({ loading: false, venue: result.venue, error: '' }); })
      .catch(error => { if (!controller.signal.aborted) setState({ loading: false, venue: null, error: error.message || 'Unable to load venue.' }); });
    return () => controller.abort();
  }, [api, venueId]);

  const venue = state.venue;
  const details = venue ? [
    ['Capacity', `${venue.capacity.toLocaleString()} people`],
    ['Address', address(venue)],
    ['Wheelchair accessible', venue.wheelchair_accessible ? 'Yes' : 'No'],
    ['Blind accessible', venue.blind_accessible ? 'Yes' : 'No'],
    ['Accessibility notes', venue.accessibility_notes || 'None specified'],
    ['Facilities', labels(venue.facilities)],
    ['Supported room layouts', labels(venue.supported_room_layouts)],
    ['Operating hours', hours(venue.operating_hours)],
    ['Default setup time', `${venue.default_setup_minutes} minutes`],
    ['Default turnaround time', `${venue.default_turnaround_minutes} minutes`],
  ] : [];

  return (
    <>
      <Navbar />
      <main className="container">
        <Link to="/venues">← All venues</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE MANAGEMENT</p>
            <h1>{venue?.venue_name || 'Venue information'}</h1>
          </div>
          <div className="venue-page-actions">
            <Link className="button-link" to={`/venues/${venueId}/edit`}>Update information</Link>
            <Link className="button-link danger-link" to={`/venues/${venueId}/delete`}>Delete venue</Link>
          </div>
        </div>
        {location.state?.message && <p className="panel venue-success" role="status">{location.state.message}</p>}
        {state.loading && <p role="status">Loading venue information…</p>}
        {state.error && <p className="panel error" role="alert">{state.error}</p>}
        {venue && <article className="panel">
          <h2>Venue characteristics</h2>
          <dl>
            {details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
        </article>}
      </main>
    </>
  );
}
