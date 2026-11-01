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
