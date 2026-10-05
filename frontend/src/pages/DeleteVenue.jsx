import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';

function when(value) {
  return value ? new Date(value).toLocaleString() : 'Date and time not specified';
}

export default function DeleteVenue() {
  const { venueId } = useParams();
  const { api } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, venue: null, events: [], confirmation: '', error: '', deleting: false });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, venue: null, events: [], confirmation: '', error: '', deleting: false });
    api(`/api/venues/${encodeURIComponent(venueId)}/deletion-check`, { cache: 'no-store', signal: controller.signal })
      .then(result => {
        if (!controller.signal.aborted) setState({ loading: false, venue: result.venue, events: result.events || [], confirmation: '', error: '', deleting: false });
      })
      .catch(error => {
        if (!controller.signal.aborted) setState({ loading: false, venue: null, events: error.data?.events || [], confirmation: '', error: error.message || 'Unable to check whether this venue can be deleted.', deleting: false });
      });
    return () => controller.abort();
  }, [api, venueId]);

  async function deleteVenue() {
    if (!state.venue || state.confirmation !== state.venue.venue_name || state.events.length) return;
    setState(current => ({ ...current, deleting: true, error: '' }));
    try {
      const result = await api(`/api/venues/${encodeURIComponent(venueId)}`, { method: 'DELETE' });
      navigate('/venues', { replace: true, state: { message: result.message } });
    } catch (error) {
      setState(current => ({ ...current, deleting: false, events: error.data?.events || current.events, error: error.message }));
    }
  }

  const blocked = state.events.length > 0;
  const confirmed = state.confirmation === state.venue?.venue_name;
  return (
    <>
      <Navbar />
      <main className="container venue-delete-page">
        <Link to={`/venues/${venueId}`}>← Venue information</Link>
        <div className="heading"><div><p className="eyebrow">VENUE MANAGEMENT</p><h1>Delete venue</h1></div></div>
        <section className="panel venue-delete-panel">
          <h2>Confirm venue deletion</h2>
          {state.loading && <p role="status">Checking venue information and upcoming events…</p>}
          {state.error && <p className="error" role="alert">{state.error}</p>}
          {state.venue && <>
            <p>You are about to permanently remove <strong>{state.venue.venue_name}</strong> from the venue catalogue.</p>
            {blocked ? <>
              <p className="venue-warning" role="alert">This venue cannot be deleted because it has upcoming scheduled events.</p>
              <ul className="venue-conflict-list">
                {state.events.map(event => <li key={event.event_id}><strong>{event.event_name || 'Untitled event'}</strong><span>{when(event.start_datetime)}</span></li>)}
              </ul>
            </> : <>
              <p>This action cannot be undone. Type the venue name exactly to confirm.</p>
              <label>
                Type <strong>{state.venue.venue_name}</strong> to confirm
                <input type="text" value={state.confirmation} onChange={event => setState(current => ({ ...current, confirmation: event.target.value }))} autoComplete="off" />
              </label>
            </>}
            <div className="venue-page-actions">
              <button type="button" className="danger-button" disabled={!confirmed || blocked || state.deleting} onClick={deleteVenue}>{state.deleting ? 'Deleting venue…' : 'Delete venue'}</button>
              <Link className="button-link secondary-link" to={`/venues/${venueId}`}>Cancel</Link>
            </div>
          </>}
          {!state.loading && !state.venue && <Link className="button-link secondary-link" to="/venues">Back to venues</Link>}
        </section>
      </main>
    </>
  );
}
