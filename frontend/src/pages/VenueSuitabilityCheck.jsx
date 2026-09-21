import { Link, useLocation, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';

export default function VenueSuitabilityCheck({ onSignOut }) {
  const { eventId } = useParams();
  const location = useLocation();
  const event = location.state?.event;

  return (
    <>
      <Navbar onSignOut={onSignOut} />
      <main className="container">
        <Link to="/venue-suitability">← Choose another event</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE PLANNING</p>
            <h1>Venue suitability check</h1>
          </div>
        </div>
        <div className="panel">
          <h2>Event selected</h2>
          <p>{event?.event_name || `Event ${eventId}`}</p>
          <p>The venue comparison and requirement results will be added here.</p>
        </div>
      </main>
    </>
  );
}
