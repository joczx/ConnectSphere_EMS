import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useAuth } from '../auth/AuthContext';

function formatDateTime(value) {
  if (!value) return 'Not specified';
  return new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Singapore',
  }).format(new Date(value));
}

function formatStatus(value) {
  if (!value) return 'Not specified';
  return value.replaceAll('_', ' ').replace(/^./, character => character.toUpperCase());
}

export default function VenueSuitability() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [state, setState] = useState({ loading: true, error: '' });

  useEffect(() => {
    const controller = new AbortController();

    async function loadEvents() {
      setState({ loading: true, error: '' });
      try {
        const data = await api('/api/events', { cache: 'no-store', signal: controller.signal });
        if (!controller.signal.aborted) {
          setEvents(data.events || []);
          setState({ loading: false, error: '' });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setEvents([]);
          setState({ loading: false, error: error.message || 'Unable to load events.' });
        }
      }
    }

    loadEvents();
    return () => controller.abort();
  }, [api]);

  return (
    <>
      <Navbar />
      <main className="container">
        <Link to="/home">← Home</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE PLANNING</p>
            <h1>Check venue suitability</h1>
          </div>
        </div>
        <p>Select an event to compare its requirements with available venue information.</p>

        {state.loading && <p role="status">Loading events…</p>}
        {state.error && <div className="panel error" role="alert">{state.error}</div>}
        {!state.loading && !state.error && events.length === 0 && (
          <div className="panel">No events are available to check yet.</div>
        )}

        {events.length > 0 && (
          <section aria-label="Choose an event">
            <h2>Select an event</h2>
            <div className="suitability-event-grid">
              {events.map(event => {
                const selected = selectedEventId === event.event_id;
                return (
                  <button
                    aria-pressed={selected}
                    className={`suitability-event-card panel${selected ? ' selected' : ''}`}
                    key={event.event_id}
                    onClick={() => setSelectedEventId(event.event_id)}
                    type="button"
                  >
                    <span className="suitability-event-selection" aria-hidden="true">{selected ? '✓' : ''}</span>
                    <span className="suitability-event-name">{event.event_name || 'Unnamed event'}</span>
                    <span>{formatDateTime(event.start_datetime)}</span>
                    <span className="metadata">Ends {formatDateTime(event.end_datetime)}</span>
                    <span className="metadata">Status: {formatStatus(event.status)}</span>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        <div className="suitability-actions">
          <button
            disabled={selectedEventId === null}
            onClick={() => navigate(
              `/venue-suitability/check/${encodeURIComponent(selectedEventId)}`,
              { state: { event: events.find(item => item.event_id === selectedEventId) } },
            )}
            type="button"
          >
            Continue to suitability check
          </button>
        </div>
      </main>
    </>
  );
}
