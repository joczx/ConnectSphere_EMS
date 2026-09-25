import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';

export default function DeleteVenue() {
  const { venueId } = useParams();
  return (
    <>
      <Navbar />
      <main className="container venue-delete-page">
        <Link to={`/venues/${venueId}`}>← Venue information</Link>
        <div className="heading"><div><p className="eyebrow">VENUE MANAGEMENT</p><h1>Delete venue</h1></div></div>
        <section className="panel venue-delete-panel">
          <h2>Confirm venue deletion</h2>
          <p>Venue details and conflicting upcoming events will be loaded here before deletion is allowed.</p>
          <p className="skeleton-note">This is a frontend skeleton. No venue can be deleted from this page yet.</p>
          <label>
            Type the venue name to confirm
            <input type="text" placeholder="Venue name" disabled />
          </label>
          <div className="venue-page-actions">
            <button type="button" className="danger-button" disabled>Delete venue</button>
            <Link className="button-link secondary-link" to={`/venues/${venueId}`}>Cancel</Link>
          </div>
        </section>
      </main>
    </>
  );
}
