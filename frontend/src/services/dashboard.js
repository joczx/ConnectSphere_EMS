import { loadEvents } from './eventLoading.js';
import { can, canViewEvent } from '../auth/access.js';

const normalize = role => role.trim().replaceAll('_', ' ').toLowerCase();
export const countStatuses = rows => rows.reduce((counts, row) => {
  counts[row.status || 'unknown'] = (counts[row.status || 'unknown'] || 0) + 1;
  return counts;
}, {});

export async function loadDashboard(api, roles, organiserId, signal) {
  const has = (...names) => roles.some(role => names.includes(normalize(role)));
  const organiser = has('event organiser', 'event organizer');
  const coordinator = has('event coordinator');
  const lead = has('event coordinator lead');
  const technical = has('technical support staff', 'technical support');
  const staff = has('venue staff');
  const sections = [];
  const warnings = [];
  const get = path => api(path, { cache: 'no-store', signal, feedback: false });
  const section = async (id, title, scope, path, statuses, read) => {
    try {
      const rows = await read();
      sections.push({ id, title, scope, path, statuses, total: rows.length, reviewed: id === 'events' || id === 'assignments' ? null : rows.filter(row => (id === 'equipment' ? ['accepted', 'partially_accepted', 'rejected', 'in_progress', 'completed'] : id === 'venues' ? ['approved', 'rejected'] : ['planning', 'rejected']).includes(row.status)).length, counts: countStatuses(rows) });
      return rows;
    } catch (error) {
      if (signal?.aborted || error.name === 'AbortError') throw error;
      warnings.push(`${title}: ${error.message || 'Unable to load.'}`);
      return null;
    }
  };
  // Loaded once. Every section shows only the events the viewer is assigned
  // to (all of them for a Coordinator Lead), and the bookings and equipment
  // requests belonging to those events.
  const loadedEvents = loadEvents(api, '/api/events', { cache: 'no-store', signal, feedback: false })
    .then(({ data, statusWarning }) => {
      if (statusWarning) warnings.push(statusWarning);
      return data.events || [];
    });
  loadedEvents.catch(() => {}); // each section reports the failure itself
  const visibleEvents = async () => (await loadedEvents).filter(event => canViewEvent(roles, organiserId, event));
  const assignedEventIds = async action => new Set((await loadedEvents)
    .filter(event => can(roles, organiserId, action, event)).map(event => String(event.event_id)));
  const requestStatuses = [['draft', 'Draft'], ['submitted', 'Submitted'], ['planning', 'Approved / planning'], ['rejected', 'Rejected'], ['cancelled', 'Cancelled']];
  const tasks = [];
  if (organiser) tasks.push(section('own-requests', 'My event requests', 'Requests you created', '/event-requests', requestStatuses,
    async () => (await get('/api/event-requests?event_organiser_id=' + encodeURIComponent(organiserId))).event_requests));
  if (coordinator) tasks.push(section('review-requests', 'Assigned event requests', 'Requests assigned to you', '/review-event-requests', requestStatuses.filter(([status]) => status !== 'draft'),
    async () => (await get('/api/event-requests')).event_requests.filter(row => row.event_coordinator_id === organiserId && row.status !== 'draft')));
  if (lead) tasks.push(section('assignments', 'Awaiting assignment', 'Submitted requests without a coordinator', '/assign-event-coordinators', [['submitted', 'To assign']],
    async () => (await get('/api/event-requests/unassigned')).event_requests.map(row => ({ ...row, status: 'submitted' }))));
  if (coordinator || staff) tasks.push(section('venues', 'Venue booking requests', staff ? 'Bookings available for your review' : 'Your venue booking requests', staff ? '/review-venue-bookings' : '/venue-bookings',
    [['submitted', 'Submitted'], ['approved', 'Approved'], ['rejected', 'Rejected'], ['cancelled', 'Cancelled']],
    async () => {
      const bookings = (await get('/api/venue-bookings')).bookings;
      if (!staff) return bookings;
      const assigned = await assignedEventIds('booking.review');
      return bookings.filter(booking => assigned.has(String(booking.event_id)));
    }));
  const eventsPromise = section('events', 'Events', 'Events visible to your account', '/events',
    [['planning', 'Planning'], ['confirmed', 'Confirmed'], ['completed', 'Completed'], ['cancelled', 'Cancelled']],
    visibleEvents);
  tasks.push(eventsPromise);
  if (technical || coordinator) tasks.push(section('equipment', 'Equipment requests', technical ? 'Requests available for your review' : 'Requests for your assigned events', technical ? '/equipment' : '/events',
    [['pending', 'Pending review'], ['accepted', 'Accepted'], ['partially_accepted', 'Partially accepted'], ['rejected', 'Rejected'], ['in_progress', 'In progress'], ['completed', 'Completed'], ['cancelled', 'Cancelled']],
    async () => {
      if (technical) {
        const requests = (await get('/api/equipment-request-reviews')).equipment_requests;
        const assigned = await assignedEventIds('equipment.review');
        return requests.filter(request => assigned.has(String(request.event_id)));
      }
      const events = await eventsPromise;
      if (!events) throw new Error('Event information is unavailable.');
      const requests = await Promise.all(events.filter(event => event.event_coordinator_id === organiserId).map(async event => (await get(`/api/events/${event.event_id}/equipment-requests`)).equipment_requests));
      return requests.flat();
    }));
  await Promise.all(tasks);
  const events = await eventsPromise;
  return { sections: sections.sort((a, b) => ['own-requests', 'review-requests', 'assignments', 'events', 'venues', 'equipment'].indexOf(a.id) - ['own-requests', 'review-requests', 'assignments', 'events', 'venues', 'equipment'].indexOf(b.id)), warnings,
    events: events || [], updatedAt: new Date().toISOString() };
}

export function upcomingEvents(events, now = Date.now()) {
  return events.filter(event => ['planning', 'confirmed'].includes(event.status) && new Date(event.end_datetime || event.start_datetime).getTime() > now)
    .sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime)).slice(0, 5);
}
