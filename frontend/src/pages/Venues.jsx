import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueCard from '../components/VenueCard';
import { useAuth } from '../auth/AuthContext';
import { VENUE_FACILITIES, VENUE_ROOM_LAYOUTS } from '../config/venueOptions';

export default function Venues() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [state, setState] = useState({ venues: [], loading: true, error: '' });
  const formRef = useRef(null);
  const isFiltered = searchParams.toString().length > 0;

  useEffect(() => {
    const controller = new AbortController();
    async function loadVenues() {
      setState(current => ({ ...current, loading: true, error: '' }));
      try {
        const path = isFiltered ? `/api/venues/search?${searchParams}` : '/api/venues/catalogue';
        const result = await api(path, { cache: 'no-store', signal: controller.signal });
        if (!controller.signal.aborted) setState({ venues: result.venues || [], loading: false, error: '' });
      } catch (error) {
        if (!controller.signal.aborted) setState({ venues: [], loading: false, error: error.message || 'Unable to load venues.' });
      }
    }
    loadVenues();
    return () => controller.abort();
  }, [api, isFiltered, searchParams]);

  function applyFilters(event) {
    event.preventDefault();
    const parameters = new URLSearchParams();
    for (const [name, value] of new FormData(event.currentTarget)) {
      if (value) parameters.append(name, value);
    }
    navigate(parameters.toString() ? `/venues?${parameters}` : '/venues');
  }

  function clearFilters() {
    formRef.current?.reset();
    navigate('/venues');
  }

  return (
    <>
      <Navbar />
      <main className="container">
        <Link to="/home">← Home</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE MANAGEMENT</p>
            <h1>All venues</h1>
          </div>
          <Link className="button-link" to="/venues/new">Create venue</Link>
        </div>
        <p>View and manage the venues available to ConnectSphere.</p>

        <form ref={formRef} className="panel venue-catalogue-filters" aria-labelledby="venue-filter-heading" onSubmit={applyFilters}>
          <div className="heading venue-section-heading">
            <h2 id="venue-filter-heading">Filter venues</h2>
            <button type="button" className="secondary" onClick={clearFilters} disabled={!isFiltered}>Clear filters</button>
          </div>
          <div className="venue-form-grid">
            <label>Venue name<input name="name" type="search" placeholder="Search by name" defaultValue={searchParams.get('name') || ''} /></label>
            <label>Location<input name="location" type="search" placeholder="Building, street or postal code" defaultValue={searchParams.get('location') || ''} /></label>
            <label>Minimum capacity<input name="capacity" type="number" min="1" placeholder="Number of people" defaultValue={searchParams.get('capacity') || ''} /></label>
            <label>Wheelchair accessibility<select name="wheelchair_accessible" defaultValue={searchParams.get('wheelchair_accessible') || ''}><option value="">Any</option><option value="true">Required</option></select></label>
            <label>Blind accessibility<select name="blind_accessible" defaultValue={searchParams.get('blind_accessible') || ''}><option value="">Any</option><option value="true">Required</option></select></label>
          </div>
          <fieldset className="venue-filter-options">
            <legend>Facilities</legend>
            <div className="facility-options">{VENUE_FACILITIES.map(([value, label]) => (
              <label className="facility-option" key={value}><input name="facilities" type="checkbox" value={value} defaultChecked={searchParams.getAll('facilities').includes(value)} />{label}</label>
            ))}</div>
          </fieldset>
          <fieldset className="venue-filter-options">
            <legend>Room layouts</legend>
            <div className="facility-options">{VENUE_ROOM_LAYOUTS.map(([value, label]) => (
              <label className="facility-option" key={value}><input name="layouts" type="checkbox" value={value} defaultChecked={searchParams.getAll('layouts').includes(value)} />{label}</label>
            ))}</div>
          </fieldset>
          <div className="venue-page-actions"><button type="submit">Apply filters</button></div>
        </form>

        <section aria-labelledby="venue-list-heading">
          <div className="heading venue-section-heading"><h2 id="venue-list-heading">Venue catalogue</h2>{!state.loading && !state.error && <span className="metadata">{state.venues.length} {state.venues.length === 1 ? 'venue' : 'venues'}</span>}</div>
          {state.loading && <p role="status">Loading venues…</p>}
          {state.error && <p className="panel error" role="alert">{state.error}</p>}
          {!state.loading && !state.error && state.venues.length === 0 && <p className="panel">{isFiltered ? 'No venues match the selected filters.' : 'No venues are currently in the catalogue.'}</p>}
          {state.venues.length > 0 && <div className="venue-card-grid">{state.venues.map(venue => <VenueCard key={venue.venue_id} venue={venue} />)}</div>}
        </section>
      </main>
    </>
  );
}
