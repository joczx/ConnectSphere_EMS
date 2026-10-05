import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueForm from '../components/VenueForm';
import { useAuth } from '../auth/AuthContext';
import { changedVenueFields, venuePayloadFromForm } from '../services/venueForm';

function draftKey(venueId) {
  return `venue-update-draft:${venueId}`;
}

function readDraft(venueId) {
  try {
    const value = localStorage.getItem(draftKey(venueId));
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

function removeDraft(venueId) {
  try { localStorage.removeItem(draftKey(venueId)); } catch { /* Storage is optional. */ }
}

export default function UpdateVenue() {
  const { venueId } = useParams();
  const { api } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, venue: null, values: null, error: '', errors: {}, notice: '' });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, venue: null, values: null, error: '', errors: {}, notice: '' });
    api(`/api/venues/${encodeURIComponent(venueId)}`, { cache: 'no-store', signal: controller.signal })
      .then(result => {
        if (controller.signal.aborted) return;
        const saved = readDraft(venueId);
        if (saved?.version === result.venue.version && saved.values) {
          setState({ loading: false, venue: result.venue, values: saved.values, error: '', errors: {}, notice: 'Your saved draft has been restored.' });
          return;
        }
        if (saved) removeDraft(venueId);
        setState({
          loading: false,
          venue: result.venue,
          values: null,
          error: '',
          errors: {},
          notice: saved ? 'The saved draft was based on older venue information, so please redo the update.' : '',
        });
      })
      .catch(error => {
        if (!controller.signal.aborted) setState({ loading: false, venue: null, values: null, error: error.message || 'Unable to load venue.', errors: {}, notice: '' });
      });
    return () => controller.abort();
  }, [api, venueId]);

  function saveDraft(data) {
    const values = venuePayloadFromForm(data);
    try {
      localStorage.setItem(draftKey(venueId), JSON.stringify({ version: state.venue.version, values }));
      setState(current => ({ ...current, values, notice: 'Draft saved on this device. You can return to finish it later.', error: '', errors: {} }));
    } catch {
      setState(current => ({ ...current, error: 'The draft could not be saved on this device. Please try again.', errors: {} }));
    }
  }

  async function updateVenue(event) {
    event.preventDefault();
    const values = venuePayloadFromForm(new FormData(event.currentTarget));
    const changes = changedVenueFields(state.venue, values);
    if (Object.keys(changes).length === 0) {
      setState(current => ({ ...current, error: 'Change at least one venue field before updating.', errors: {} }));
      return;
    }

    setState(current => ({ ...current, submitting: true, error: '', errors: {}, notice: '' }));
    try {
      const result = await api(`/api/venues/${encodeURIComponent(venueId)}`, {
        method: 'PATCH',
        body: { version: state.venue.version, ...changes },
      });
      removeDraft(venueId);
      navigate(`/venues/${venueId}`, { replace: true, state: { message: result.message } });
    } catch (error) {
      if (error.data?.venue) {
        removeDraft(venueId);
        setState({
          loading: false,
          submitting: false,
          venue: error.data.venue,
          values: null,
          error: error.message,
          errors: {},
          notice: 'The update form has been reset with the current venue information.',
        });
      } else {
        setState(current => ({ ...current, submitting: false, error: error.message, errors: error.details || {} }));
      }
    }
  }

  const initialVenue = state.values || state.venue;
  return (
    <>
      <Navbar />
      <main className="container">
        <Link to={`/venues/${venueId}`}>← Venue information</Link>
        <div className="heading"><div><p className="eyebrow">VENUE MANAGEMENT</p><h1>Update venue</h1></div></div>
        <p>Change one or more venue fields. You can save a draft and return to it on this device.</p>
        {state.notice && <p className="panel venue-success" role="status">{state.notice}</p>}
        {state.loading && <p role="status">Loading venue information…</p>}
        {!state.loading && !state.venue && <p className="panel error" role="alert">{state.error}</p>}
        {initialVenue && <VenueForm
          key={`${state.venue.version}:${state.values ? 'draft' : 'current'}`}
          mode="update"
          venueId={venueId}
          initialVenue={initialVenue}
          onSubmit={updateVenue}
          onSaveDraft={saveDraft}
          submitting={Boolean(state.submitting)}
          error={state.error}
          errors={state.errors}
        />}
      </main>
    </>
  );
}
