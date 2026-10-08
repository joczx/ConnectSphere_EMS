import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueSearchBar from '../components/VenueSearchBar';
import EventVenueContext from '../components/EventVenueContext';
import VenueResults from '../components/VenueResults';
import VenueFilterForm from '../components/VenueFilterForm';
import { useAuth } from '../auth/AuthContext';
import {
  APPLIED_KEY, EVENT_KEY, activeFilters, hasFilters, matchesEventFilters, pageUrl,
  searchPath, withEvent, withEventFilters, withoutChip, withoutFilters,
} from '../services/venueSearch';

export default function VenueSearch() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const eventId = params.get(EVENT_KEY) || '';

  const [events, setEvents] = useState([]);
  const [context, setContext] = useState(null);
  const [results, setResults] = useState({ venues: [], loading: true, error: '' });
  const [filtersOpen, setFiltersOpen] = useState(false);

  // The events this coordinator could be planning a venue for. Loaded whether
  // or not one is already chosen, so the context can be switched here.
  useEffect(() => {
    const controller = new AbortController();
    api('/api/events', { cache: 'no-store', signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setEvents(data.events || []); })
      .catch(() => { if (!controller.signal.aborted) setEvents([]); });
    return () => controller.abort();
  }, [api]);

  // What the chosen event needs from a venue. The filters come back in the
  // shape the search endpoint accepts, so the page never restates the rules.
  useEffect(() => {
    if (!eventId) {
      setContext(null);
      return undefined;
    }
    const controller = new AbortController();
    setContext(null);
    api(`/api/events/${encodeURIComponent(eventId)}/venue-criteria`, {
      cache: 'no-store', signal: controller.signal,
    })
      .then(data => { if (!controller.signal.aborted) setContext(data); })
      .catch(error => {
        if (!controller.signal.aborted) {
          setContext({ error: error.message || 'Unable to load this event.' });
        }
      });
    return () => controller.abort();
  }, [api, eventId]);

  // Opening the search from an event applies that event's requirements once.
  // The marker is what makes it once: without it, clearing the filters would be
  // undone on the next render.
  useEffect(() => {
    if (!context?.filters || params.get(APPLIED_KEY)) return;
    navigate(pageUrl(withEventFilters(params, context.filters)), { replace: true });
  }, [context, navigate, params]);

  useEffect(() => {
    // Hold the list until the event's filters have been applied, so the first
    // thing the coordinator sees is the filtered catalogue rather than all
    // venues flashing past.
    if (eventId && !params.get(APPLIED_KEY)) {
      // Unless they can never arrive, in which case stop waiting for them and
      // let the error below stand on its own.
      if (context?.error) setResults({ venues: [], loading: false, error: '' });
      return undefined;
    }

    const controller = new AbortController();
    setResults(current => ({ ...current, loading: true, error: '' }));
    api(searchPath(params), { cache: 'no-store', signal: controller.signal })
      .then(data => {
        if (!controller.signal.aborted) {
          setResults({
            venues: data.venues || [], eligibleCount: data.eligible_count,
            loading: false, error: '',
          });
        }
      })
      .catch(error => {
        if (!controller.signal.aborted) {
          setResults({ venues: [], loading: false, error: error.message || 'Unable to search venues.' });
        }
      });
    return () => controller.abort();
  }, [api, params, eventId, context]);

  const chips = activeFilters(params);
  const filtersApplied = hasFilters(params);
  const filtersMatchEvent = !!context?.filters && matchesEventFilters(params, context.filters);
  const go = (next) => navigate(pageUrl(next));

  return (
    <>
      <Navbar searchBar={<VenueSearchBar />} />
      <main className="container">
        {eventId
          ? <Link to={`/events/${encodeURIComponent(eventId)}`}>← Back to event planning</Link>
          : <Link to="/home">← Home</Link>}
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE SEARCH</p>
            <h1>Venue catalogue</h1>
          </div>
        </div>
        <p>
          Search by venue name, or use filters to narrow the results. All dates and times are
          Singapore time (SGT).
        </p>

        {context?.error && <div className="panel error" role="alert">
          <p>{context.error}</p>
          <button type="button" className="secondary" onClick={() => go(withEvent(params, ''))}>
            Browse all venues instead
          </button>
        </div>}

        {/* Held back until the event is known, so the page never describes the
            requirements of an event it has not read yet. */}
        {eventId && !context && <p className="panel" role="status">Loading the event you are planning…</p>}

        {(!eventId || context?.requirements) && <EventVenueContext
          events={events}
          eventId={eventId}
          event={context?.event}
          requirements={context?.requirements || []}
          planningNote={context?.planning_note}
          filtersMatchEvent={filtersMatchEvent}
          onSelectEvent={(nextEventId) => go(withEvent(params, nextEventId))}
          onApplyRequirements={() => go(withEventFilters(params, context.filters))}
        />}

        <section className="panel venue-filter-summary" aria-labelledby="active-filters-heading">
          <div className="heading venue-section-heading">
            <h2 id="active-filters-heading">Filters</h2>
            <div className="venue-page-actions">
              <button
                type="button"
                aria-expanded={filtersOpen}
                aria-controls="venue-filter-form"
                onClick={() => setFiltersOpen(open => !open)}
              >
                {filtersOpen ? 'Hide filters' : filtersApplied ? 'Edit filters' : 'Add filters'}
              </button>
              <button
                type="button"
                className="secondary"
                disabled={!filtersApplied}
                onClick={() => go(withoutFilters(params))}
              >
                Clear filters
              </button>
            </div>
          </div>
          {!filtersApplied && (
            <p className="metadata">
              No filters applied. Every venue in the catalogue is listed. Use Add filters to narrow it down.
            </p>
          )}
          {filtersApplied && (
            <ul className="venue-filter-chips">
              {chips.map(chip => (
                <li key={chip.id}>
                  <button type="button" onClick={() => go(withoutChip(params, chip))}>
                    {chip.label} <span aria-hidden="true">×</span>
                    <span className="sr-only">Remove this filter</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {/* Keyed on the URL so it always opens showing the filters in force,
              including after a chip is removed or the event is switched. */}
          {filtersOpen && <div id="venue-filter-form" className="venue-inline-filters">
            <VenueFilterForm
              key={params.toString()}
              params={params}
              onApply={(next) => { setFiltersOpen(false); go(next); }}
              onCancel={() => setFiltersOpen(false)}
            />
          </div>}
        </section>

        <VenueResults
          venues={results.venues}
          eventId={eventId}
          canRequest={context ? context.planning !== false : true}
          eligibleCount={results.eligibleCount}
          loading={results.loading}
          error={results.error}
          emptyMessage={filtersApplied
            ? 'No venues match the current filters. Clear a filter to widen the search.'
            : 'No venues are currently in the catalogue.'}
        />
      </main>
    </>
  );
}
