import { useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';

export default function VenueSearch({ onSignOut }) {
  const [query, setQuery] = useState('');
  const [hasSearched, setHasSearched] = useState(false);

  function searchVenues(event) {
    event.preventDefault();
    // TODO: Send the keyword and any active filters to the venue-search API.
    setHasSearched(true);
  }

  return (
    <>
      <Navbar onSignOut={onSignOut} />
      <main className="container">
        <Link to="/home">← All applications</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE SEARCH</p>
            <h1>Venue search</h1>
          </div>
          <Link className="button-link" to="/venue-search/filters">
            Filters
          </Link>
        </div>
        <p>Search by venue name or location, or use filters to narrow the results.</p>
        <form className="venue-keyword-search" onSubmit={searchVenues}>
          <label className="sr-only" htmlFor="venue-query">Search venues</label>
          <input
            id="venue-query"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by venue name or location"
          />
          <button type="submit">Search</button>
        </form>
        <section className="panel" aria-labelledby="venue-results-heading">
          <h2 id="venue-results-heading">Search results</h2>
          <p>
            {hasSearched
              ? 'Venue results will appear here when the venue-search backend is connected.'
              : 'Start with a keyword search, or select Filters for detailed event requirements.'}
          </p>
        </section>
      </main>
    </>
  );
}
