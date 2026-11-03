import { loadEvents, eventWorkspaceItems } from './eventLoading.js';
import { countStatuses } from './dashboard.js';

export async function loadOrganiserDashboard(api, organiserId, signal, now = Date.now()) {
  if (!organiserId) throw new Error('Unable to identify your account. Please sign in again.');
  const get = path => api(path, { signal, cache: 'no-store', feedback: false });
  const results = await Promise.allSettled([
    loadEvents(api, '/api/events', { signal, cache: 'no-store', feedback: false }),
    get('/api/event-requests?event_organiser_id=' + encodeURIComponent(organiserId)),
    get('/api/notifications?limit=5'),
  ]);
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  const warnings = [];
  const [eventResult, requestResult, updateResult] = results;
  for (const [index, title] of ['Events', 'Event requests', 'Recent updates'].entries()) {
    if (results[index].status === 'rejected') {
      if (results[index].reason.name === 'AbortError') throw results[index].reason;
      warnings.push(`${title}: ${results[index].reason.message || 'Unable to load.'}`);
    }
  }
  const events = eventResult.status === 'fulfilled' ? (eventResult.value.data.events || []).filter(item => item.event_organiser_id === organiserId) : [];
  const requests = requestResult.status === 'fulfilled' ? (requestResult.value.event_requests || []).filter(item => item.event_organiser_id === organiserId) : [];
  if (eventResult.value?.statusWarning) warnings.push(eventResult.value.statusWarning);
  const items = eventWorkspaceItems(events, requests, organiserId);
  const counts = eventResult.status === 'fulfilled' && requestResult.status === 'fulfilled' ? countStatuses(items) : null;
  const upcoming = events.filter(item => ['planning', 'pending_safety_checks', 'confirmed'].includes(item.status)
    && Date.parse(item.start_datetime) > now).sort((left, right) => Date.parse(left.start_datetime) - Date.parse(right.start_datetime));
  const attention = items.filter(item => item.workspace_type === 'request' && ['draft', 'rejected'].includes(item.status))
    .map(item => ({ key: item.workspace_key, name: item.event_name || 'Untitled request',
      action: item.status === 'draft' ? 'Finish draft request' : 'Amend rejected request', path: item.workspace_path }));
  attention.push(...upcoming.filter(item => !item.registration_opens_at || !item.registration_closes_at)
    .map(item => ({ key: 'registration-' + item.event_id, name: item.event_name, action: 'Set registration dates', path: '/events/' + item.event_id })));

  const rosters = await Promise.all(upcoming.map(async item => {
    try {
      const data = await get(`/api/events/${item.event_id}/registrations`);
      return { eventId: item.event_id, confirmed: data.total_registered, waitlisted: data.total_waitlisted, withdrawn: data.total_withdrawn };
    } catch (error) {
      if (signal?.aborted || error.name === 'AbortError') throw error;
      warnings.push(`Registration totals for ${item.event_name}: ${error.message || 'Unable to load.'}`);
      return null;
    }
  }));
  const registrationSummary = eventResult.status === 'fulfilled' && rosters.every(Boolean)
    ? rosters.reduce((total, item) => ({ confirmed: total.confirmed + item.confirmed, waitlisted: total.waitlisted + item.waitlisted,
      withdrawn: total.withdrawn + item.withdrawn }), { confirmed: 0, waitlisted: 0, withdrawn: 0 }) : null;
  const nextEvents = await Promise.all(upcoming.slice(0, 5).map(async item => {
    let venues;
    try {
      const data = await get(`/api/venue-bookings/events/${item.event_id}`);
      venues = [...new Set((data.bookings || []).filter(booking => booking.status === 'approved').map(booking => booking.venue_name).filter(Boolean))];
    } catch (error) {
      if (signal?.aborted || error.name === 'AbortError') throw error;
      warnings.push(`Venue for ${item.event_name}: ${error.message || 'Unable to load.'}`);
      venues = null;
    }
    return { ...item, venues, registrations: rosters.find(roster => roster?.eventId === item.event_id) || null };
  }));
  return { counts, attention, upcoming: nextEvents, registrationSummary,
    updates: updateResult.status === 'fulfilled' ? updateResult.value.items || [] : null,
    warnings, eventsAvailable: eventResult.status === 'fulfilled', updatedAt: new Date().toISOString() };
}
