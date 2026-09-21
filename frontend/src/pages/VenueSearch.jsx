import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueSearchBar from '../components/VenueSearchBar';

export default function VenueSearch({ onSignOut }) {
  return (
    <>
      <Navbar onSignOut={onSignOut} searchBar={<VenueSearchBar />} />
      <main className="container">
        <Link to="/home">← Home</Link>
        <div className="heading">
          <h1>Venue search</h1>
          <Link className="button-link" to="/venue-search/filters">Filters</Link>
        </div>
        <p>Search by venue name, or use filters to narrow the results.</p>
      </main>
    </>
  );
}
