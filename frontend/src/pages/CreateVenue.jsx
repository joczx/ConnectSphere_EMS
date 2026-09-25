import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueForm from '../components/VenueForm';

export default function CreateVenue() {
  return (
    <>
      <Navbar />
      <main className="container">
        <Link to="/venues">← All venues</Link>
        <div className="heading"><div><p className="eyebrow">VENUE MANAGEMENT</p><h1>Create venue</h1></div></div>
        <p>Add a new venue and its operational characteristics to the catalogue.</p>
        <VenueForm mode="create" />
      </main>
    </>
  );
}
