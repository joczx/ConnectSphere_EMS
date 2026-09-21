import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueSearchBar from '../components/VenueSearchBar';

export default function VenueSearchResults({ token, onRefreshSession, onSignOut }) {
  const [venues, setVenues] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchParams] = useSearchParams();
  const isFilterSearch = searchParams.get('filter') === 'true';
  const name = searchParams.get('name');

  useEffect(() => {
    if (!isFilterSearch && !name) return undefined;
    const controller = new AbortController();

    async function search() {
      const path = isFilterSearch
        ? '/api/venues/search?' + searchParams
        : '/api/venues?name=' + encodeURIComponent(name);
      const send = (accessToken) => fetch(path, {
        cache: 'no-store', signal: controller.signal,
        headers: { Authorization: 'Bearer ' + accessToken },
      });
      setLoading(true);
      setError('');
      let response = await send(token);
      if (response.status === 401) {
        const refreshedToken = await onRefreshSession();
        if (!refreshedToken) throw new Error('Your session has expired. Please sign in again.');
        response = await send(refreshedToken);
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Unable to search venues. Please try again.');
      if (!controller.signal.aborted) setVenues(result.venues);
    }

    search().catch((searchError) => {
      if (!controller.signal.aborted) {
        setVenues([]);
        setError(searchError.message);
      }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [isFilterSearch, name, searchParams, token]);

  const filtersPath = searchParams.toString() ? `/venue-search/filters?${searchParams}` : '/venue-search/filters';

  return (
    <>
      <Navbar onSignOut={onSignOut} searchBar={<VenueSearchBar />} />
      <main className="container">
        <Link to="/home">← Home</Link>
        <div className="heading">
          <h1>Search results</h1>
          <Link className="button-link" to={filtersPath}>Filters</Link>
        </div>
        {error && <p className="panel error" role="alert">{error}</p>}
        {loading && <p>Searching…</p>}
        {!loading && !error && (isFilterSearch || name) && !venues.length && <p className="panel">No venues found.</p>}
        {venues.length > 0 && <ul className="venue-results">
          {venues.map((venue) => <li key={venue.venue_id}>
            <h2>{venue.venue_name}</h2>
            <p>{venue.capacity.toLocaleString()} people · {venue.building_name || `${venue.block_number} ${venue.street_name}`}</p>
          </li>)}
        </ul>}
      </main>
    </>
  );
}
