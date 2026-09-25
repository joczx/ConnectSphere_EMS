import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';

const details = [
  ['Venue ID', 'Loaded from the selected venue'],
  ['Capacity', '—'],
  ['Address', '—'],
  ['Building and unit', '—'],
  ['Wheelchair accessible', '—'],
  ['Blind accessible', '—'],
  ['Accessibility notes', '—'],
  ['Facilities', '—'],
  ['Supported room layouts', '—'],
  ['Operating hours', '—'],
  ['Default setup time', '—'],
  ['Default turnaround time', '—'],
];

export default function VenueDetails() {
  const { venueId } = useParams();

  return (
    <>
      <Navbar />
      <main className="container">
        <Link to="/venues">← All venues</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE MANAGEMENT</p>
            <h1>Venue information</h1>
          </div>
          <div className="venue-page-actions">
            <Link className="button-link" to={`/venues/${venueId}/edit`}>Update information</Link>
            <Link className="button-link danger-link" to={`/venues/${venueId}/delete`}>Delete venue</Link>
          </div>
        </div>
        <p className="skeleton-note">This skeleton will load all characteristics for venue <code>{venueId}</code>.</p>
        <article className="panel">
          <h2>Selected venue</h2>
          <dl>
            {details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
        </article>
      </main>
    </>
  );
}
