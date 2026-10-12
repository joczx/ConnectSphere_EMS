// The venue search URL, shared by the catalogue page and the filter form.
//
// The URL is the single source of truth for a search: which filters are
// applied, and which event the coordinator is planning for. Keeping the reading
// and writing of it here stops the two pages disagreeing about how a filter is
// spelled, and makes a search shareable and survivable across back and forward.

import { VENUE_FACILITIES, VENUE_ROOM_LAYOUTS } from '../config/venueOptions';

// Exactly what the search endpoint accepts. Anything else in the URL is page
// state and must never be forwarded as a filter.
const SINGLE_FILTERS = [
  'name', 'location', 'capacity', 'start_date', 'end_date',
  'wheelchair_accessible', 'blind_accessible',
];
const LIST_FILTERS = ['layouts', 'facilities'];

export const EVENT_KEY = 'event_id';

// Set once the event's own requirements have been turned into filters, so
// clearing them is not immediately undone by applying them again.
export const APPLIED_KEY = 'applied';

const LAYOUT_LABELS = new Map(VENUE_ROOM_LAYOUTS);
const FACILITY_LABELS = new Map(VENUE_FACILITIES);

export function searchPath(params) {
  const query = new URLSearchParams();
  for (const key of SINGLE_FILTERS) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  for (const key of LIST_FILTERS) {
    for (const value of params.getAll(key)) if (value) query.append(key, value);
  }
  const eventId = params.get(EVENT_KEY);
  if (eventId) query.set(EVENT_KEY, eventId);
  const suffix = query.toString();
  return suffix ? `/api/venues/search?${suffix}` : '/api/venues/search';
}

export function hasFilters(params) {
  return [...SINGLE_FILTERS, ...LIST_FILTERS].some(key => params.getAll(key).some(Boolean));
}

// One removable chip per condition in force. A date range is a single chip
// because the search refuses half of one.
export function activeFilters(params) {
  const chips = [];
  const value = key => params.get(key) || '';

  if (value('name')) chips.push({ id: 'name', label: `Name contains “${value('name')}”`, drop: [['name']] });
  if (value('location')) chips.push({ id: 'location', label: `Location “${value('location')}”`, drop: [['location']] });
  if (value('capacity')) chips.push({ id: 'capacity', label: `Holds at least ${value('capacity')}`, drop: [['capacity']] });
  if (value('start_date') || value('end_date')) {
    const period = value('start_date') === value('end_date')
      ? value('start_date') : `${value('start_date')} to ${value('end_date')}`;
    chips.push({ id: 'dates', label: `Open ${period}`, drop: [['start_date'], ['end_date']] });
  }
  if (value('wheelchair_accessible')) {
    chips.push({ id: 'wheelchair', label: 'Wheelchair accessible', drop: [['wheelchair_accessible']] });
  }
  if (value('blind_accessible')) {
    chips.push({ id: 'blind', label: 'Blind accessible', drop: [['blind_accessible']] });
  }
  for (const layout of params.getAll('layouts')) {
    chips.push({
      id: `layout-${layout}`,
      label: `Layout: ${LAYOUT_LABELS.get(layout) || layout}`,
      drop: [['layouts', layout]],
    });
  }
  for (const facility of params.getAll('facilities')) {
    chips.push({
      id: `facility-${facility}`,
      label: `Facility: ${FACILITY_LABELS.get(facility) || facility}`,
      drop: [['facilities', facility]],
    });
  }
  return chips;
}

export function withoutChip(params, chip) {
  const next = new URLSearchParams(params);
  for (const [key, only] of chip.drop) {
    if (only === undefined) {
      next.delete(key);
      continue;
    }
    const kept = next.getAll(key).filter(value => value !== only);
    next.delete(key);
    for (const value of kept) next.append(key, value);
  }
  return next;
}

// Clearing the filters keeps the event. The coordinator is then looking at the
// whole catalogue while still planning for that event, which is allowed: the
// event decides what may be requested, not what may be read.
export function withoutFilters(params) {
  const next = new URLSearchParams(params);
  for (const key of [...SINGLE_FILTERS, ...LIST_FILTERS]) next.delete(key);
  return next;
}

export function withEvent(params, eventId) {
  const next = withoutFilters(params);
  next.delete(APPLIED_KEY);
  if (eventId) next.set(EVENT_KEY, String(eventId));
  else next.delete(EVENT_KEY);
  return next;
}

// Turn the requirements the server derived from the event into filters. Its
// shape is the endpoint's own, so a new filter needs no change on this side.
export function withEventFilters(params, filters) {
  const next = withoutFilters(params);
  for (const [key, value] of Object.entries(filters || {})) {
    if (Array.isArray(value)) for (const item of value) next.append(key, item);
    else if (value) next.set(key, value);
  }
  next.set(APPLIED_KEY, '1');
  return next;
}

// True when the URL still carries exactly the event's requirements, so the page
// can offer to put them back once they have been changed or cleared.
export function matchesEventFilters(params, filters) {
  const signature = (source) => [...SINGLE_FILTERS, ...LIST_FILTERS]
    .map(key => `${key}=${source.getAll(key).slice().sort().join(',')}`)
    .join('&');
  return signature(params) === signature(withEventFilters(new URLSearchParams(), filters));
}

export function pageUrl(params) {
  const suffix = params.toString();
  return suffix ? `/venue-search?${suffix}` : '/venue-search';
}
