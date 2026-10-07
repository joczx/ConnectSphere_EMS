import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { Alert, AlertTitle, AlertDescription } from '../components/Alert';
import { useAuth } from '../auth/AuthContext';

const formatTime = (value) => new Date(value).toLocaleString('en-SG', { timeZone: 'Asia/Singapore' });

export default function VenueBookings() {
  const { api } = useAuth();
  const [params] = useSearchParams();
  const [form, setForm] = useState({ venue_id: params.get('venue_id') || '', event_name: '', starts_at: '', ends_at: '', attendance: '', venue_requirements: '' });
  const [data, setData] = useState(null);
  const [venues, setVenues] = useState([]);
  const [error, setError] = useState('');
  const [confirmation, setConfirmation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const submitting = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setData(null);
    (async () => {
      const result = await api('/api/venue-bookings', { signal: controller.signal });
      const catalogue = result.can_submit
        ? await api('/api/venues/search', { signal: controller.signal }) : { venues: [] };
      if (!controller.signal.aborted) { setData(result); setVenues(catalogue.venues); }
    })().catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [api, version]);

  function change(event) {
    setForm((previous) => ({ ...previous, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (submitting.current) return;
    setError('');
    const starts = new Date(form.starts_at + '+08:00');
    const ends = new Date(form.ends_at + '+08:00');
    if (!Number.isFinite(starts.getTime()) || !Number.isFinite(ends.getTime()) || starts <= new Date() || ends <= starts) {
      setError('Choose a future start and an end after the start. Times are in Singapore time.');
      return;
    }
    submitting.current = true;
    setBusy(true);
    try {
      const result = await api('/api/venue-bookings', { method: 'POST', body: {
        ...form, attendance: Number(form.attendance), starts_at: starts.toISOString(), ends_at: ends.toISOString(),
      } });
      setConfirmation(result.booking);
      const venue = venues.find((item) => item.venue_id === result.booking.venue_id);
      setData((previous) => ({ ...previous, bookings: [{ ...result.booking, venue_name: venue?.venue_name }, ...previous.bookings] }));
    } catch (err) {
      setError([err.message, ...Object.values(err.details || {})].join(' '));
    } finally { submitting.current = false; setBusy(false); }
  }

  return <><Navbar /><main className="container">
    <Link to="/home">← Home</Link>
    <div className="heading"><h1>Venue booking requests</h1><button type="button" className="secondary" disabled={busy} onClick={() => setVersion((value) => value + 1)}>Refresh requests</button></div>
    {!data && !error && <p role="status">Loading booking requests…</p>}
    {confirmation && <section className="panel" role="status">
      <h2>Booking request submitted</h2><p>Venue Staff can now review your request. Your booking is awaiting review.</p>
      <p>Reference: {confirmation.booking_id}</p>
      <button type="button" onClick={() => { setConfirmation(null); setForm({ venue_id: '', event_name: '', starts_at: '', ends_at: '', attendance: '', venue_requirements: '' }); }}>Create another request</button>
    </section>}
    {data?.can_submit && !confirmation && <form className="panel" onSubmit={submit}>
      <h2>Submit a booking request</h2>
      <p>All fields are required. Dates and times use Singapore time (UTC+8).</p>
      <fieldset disabled={busy}>
        <label>Venue<select name="venue_id" required value={form.venue_id} onChange={change}>
          <option value="">Select a venue</option>{venues.map((venue) => <option key={venue.venue_id} value={venue.venue_id}>{venue.venue_name}</option>)}
        </select></label>
        <label>Event name<input name="event_name" required maxLength={200} value={form.event_name} onChange={change} /></label>
        <div className="search-filter-grid">
          <label>Start date and time<input type="datetime-local" name="starts_at" required value={form.starts_at} onChange={change} /></label>
          <label>End date and time<input type="datetime-local" name="ends_at" required value={form.ends_at} onChange={change} /></label>
        </div>
        <label>Expected attendance<input type="number" name="attendance" required min="1" max="2147483647" step="1" value={form.attendance} onChange={change} /></label>
        <label>Venue requirements<textarea name="venue_requirements" required maxLength={5000} rows={4} placeholder="Room layout, facilities, accessibility and setup needs. Enter ‘None’ if no special requirements." value={form.venue_requirements} onChange={change} /></label>
        <button type="submit">{busy ? 'Submitting…' : 'Submit booking request'}</button>
      </fieldset>
    </form>}
    {error && <Alert variant="destructive" className="page-alert"><AlertTitle>Unable to complete request</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
    {data && <section>
      <h2>{data.can_review ? 'Venue Staff review queue' : 'Your submitted requests'}</h2>
      <p>Dates and times below are in Singapore time (UTC+8).</p>
      {!data.bookings.length && <p className="panel">No booking requests yet.</p>}
      <div className="event-list">{data.bookings.map((booking) => <article className="panel" key={booking.booking_id}>
        <h3>{booking.event_name}</h3><p>{booking.venue_name} · Submitted</p>
        <dl><div><dt>Start</dt><dd>{formatTime(booking.starts_at)}</dd></div>
          <div><dt>End</dt><dd>{formatTime(booking.ends_at)}</dd></div>
          <div><dt>Attendance</dt><dd>{booking.attendance}</dd></div>
          <div><dt>Submitted</dt><dd>{formatTime(booking.submitted_at)}</dd></div>
          <div><dt>Venue requirements</dt><dd>{booking.venue_requirements}</dd></div>
        </dl><p>Reference: {booking.booking_id}</p>
      </article>)}</div>
    </section>}
  </main></>;
}
