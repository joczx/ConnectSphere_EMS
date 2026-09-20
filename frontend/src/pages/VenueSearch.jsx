import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';

export default function VenueSearch({ token, onRefreshSession, onSignOut }) {
  const [query, setQuery] = useState('');
  const [hasSearched, setHasSearched] = useState(false);
  const [venues, setVenues] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const isFilterSearch = searchParams.get('filter') === 'true';

  async function requestVenues(path, controller) {
    const send = (accessToken) => fetch(path, {
      cache: 'no-store',
      signal: controller?.signal,
      headers: { Authorization: 'Bearer ' + accessToken },
    });
    let response = await send(token);
    if (response.status === 401) {
      const refreshedToken = await onRefreshSession();
      if (!refreshedToken) throw new Error('Your session has expired. Please sign in again.');
      response = await send(refreshedToken);
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Unable to search venues. Please try again.');
    return result.venues;
  }

  useEffect(() => {
    if (!isFilterSearch) return undefined;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setHasSearched(true);
    requestVenues('/api/venues/search?' + searchParams.toString(), controller)
      .then((results) => { if (!controller.signal.aborted) setVenues(results); })
      .catch((searchError) => {
        if (!controller.signal.aborted) {
          setVenues([]);
          setError(searchError.message);
        }
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [isFilterSearch, searchParams, token]);

  async function searchVenues(event) {
    event.preventDefault();
    const name = query.trim();
    if (!name) {
      setError('Enter a venue name to search.');
      return;
    }

    setSearchParams({});
    setLoading(true);
    setError('');
    setHasSearched(true);
    try {
      setVenues(await requestVenues('/api/venues?name=' + encodeURIComponent(name)));
    } catch (searchError) {
      setVenues([]);
      setError(searchError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Navbar onSignOut={onSignOut} />
      <main className="container">
        <Link to="/home">← All applications</Link>
        <div className="heading">
          <h1>Venue search</h1>
          <Link className="button-link" to={isFilterSearch ? `/venue-search/filters?${searchParams}` : '/venue-search/filters'}>
            Filters
          </Link>
        </div>
        <p>Search by venue name, or use filters to narrow the results.</p>
        <form className="venue-keyword-search" onSubmit={searchVenues}>
          <label className="sr-only" htmlFor="venue-query">Search venues</label>
          <input
            id="venue-query"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by venue name"
          />
          <button type="submit" disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
        </form>
        {error && <p className="panel error" role="alert">{error}</p>}
        <section className="panel" aria-labelledby="venue-results-heading">
          <h2 id="venue-results-heading">Search results</h2>
          {!hasSearched && <p>Start with a keyword search, or select Filters for detailed event requirements.</p>}
          {hasSearched && !loading && !error && !venues.length && <p>
            {isFilterSearch ? 'No venues found for the selected filters.' : 'No venues found.'}
          </p>}
          {venues.length > 0 && <ul className="venue-results">
            {venues.map((venue) => <li key={venue.venue_id}>
              <h3>{venue.venue_name}</h3>
              <p>{venue.capacity.toLocaleString()} people · {venue.building_name || `${venue.block_number} ${venue.street_name}`}</p>
            </li>)}
          </ul>}
        </section>
      </main>
    </>
  );
}
