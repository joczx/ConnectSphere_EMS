import { Link, useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueForm from '../components/VenueForm';

export default function UpdateVenue() {
  const { venueId } = useParams();
  return (
    <>
      <Navbar />
      <main className="container">
        <Link to={`/venues/${venueId}`}>← Venue information</Link>
        <div className="heading"><div><p className="eyebrow">VENUE MANAGEMENT</p><h1>Update venue</h1></div></div>
        <p>Change one or more venue fields, or save the form to complete later.</p>
        <div className="panel venue-warning" role="note">Upcoming events using this venue will be shown here before an update is submitted.</div>
        <VenueForm mode="update" venueId={venueId} />
      </main>
    </>
  );
}
