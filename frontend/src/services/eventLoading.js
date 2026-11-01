export async function loadEvents(api, path, options = {}) {
  let statusWarning = '';
  try {
    await api('/api/events/status-refresh', {
      method: 'POST', body: {}, signal: options.signal, feedback: false,
    });
  } catch (error) {
    if (options.signal?.aborted || error.name === 'AbortError' || error.status < 500 || !error.status) throw error;
    statusWarning = 'Automatic status updates are unavailable. Event stages may be out of date. ' + error.message;
  }
  const data = await api(path, options);
  return { data, statusWarning };
}

export async function loadEventWorkspace(api, path, options = {}, organiserId = null) {
  const requests = organiserId ? api('/api/event-requests?event_organiser_id=' + encodeURIComponent(organiserId), {
    cache: 'no-store', signal: options.signal, feedback: false,
  }).then(data => ({ requests: data.event_requests || [] })).catch(error => {
    if (options.signal?.aborted || error.name === 'AbortError') throw error;
    return { requests: [], warning: 'Your event requests could not be loaded. ' + error.message };
  }) : Promise.resolve({ requests: [] });
  const [events, submitted] = await Promise.all([loadEvents(api, path, options), requests]);
  return { ...events, data: { ...events.data, event_requests: submitted.requests }, requestWarning: submitted.warning };
}

export function eventWorkspaceItems(events, requests, organiserId) {
  const represented = new Set(events.map(event => String(event.event_request_id)));
  return [...events, ...requests.filter(request => request.event_organiser_id === organiserId
    && !represented.has(String(request.event_request_id)))
    .map(request => ({ ...request, workspace_type: 'request', workspace_key: 'request-' + request.event_request_id,
      workspace_path: '/event-requests/' + request.event_request_id }))];
}
