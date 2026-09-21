import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

export default function VenueSearchBar() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('name') || '');

  useEffect(() => setQuery(searchParams.get('name') || ''), [searchParams]);

  function openResults(nextQuery) {
    const parameters = new URLSearchParams(searchParams);
    if (nextQuery) parameters.set('name', nextQuery);
    else parameters.delete('name');
    const suffix = parameters.toString();
    navigate(suffix ? `/venue-search/results?${suffix}` : '/venue-search');
  }

  function submit(event) {
    event.preventDefault();
    const name = query.trim();
    if (name) openResults(name);
  }

  return (
    <form className="venue-search-bar" onSubmit={submit}>
      <div className="venue-search-bar-content">
        <label className="sr-only" htmlFor="venue-query">Search venues</label>
        <input id="venue-query" onChange={(event) => setQuery(event.target.value)} placeholder="Search by venue name" type="text" value={query} />
        {query && <button aria-label="Clear search" className="venue-search-clear" onClick={() => setQuery('')} type="button">×</button>}
        <button aria-label="Search venues" className="venue-search-submit" type="submit">
          <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6" /><path d="m16 16 5 5" /></svg>
        </button>
      </div>
    </form>
  );
}
