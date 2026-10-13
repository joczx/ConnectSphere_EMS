export function actionMessage(url, method, data) {
  if (data?.message && Array.isArray(data.notified) && data.notified.length === 0) {
    return data.message.replace(/The Event Organiser has been notified\.|The Event Coordinator has been notified\./g, 'Notification delivery could not be confirmed.');
  }
  if (data?.message) return data.message;
  const path = url.split('?')[0];
  if (path.endsWith('/registration-readiness')) return `Registration readiness saved. Event status: ${data?.event?.status || 'updated'}.`;
  if (path.endsWith('/coordinator')) return 'Event Coordinator reassigned successfully.';
  if (path.endsWith('/alerts/dismiss')) return 'Notifications dismissed.';
  if (path.endsWith('/review') || path.includes('equipment-request-reviews')) return 'Review decision recorded successfully.';
  if (path.endsWith('/cancel')) return 'Cancellation recorded successfully.';
  if (path.includes('/equipment/reservations')) return method === 'DELETE' ? 'Equipment reservation cancelled.' : method === 'PATCH' ? 'Equipment reservation updated.' : 'Equipment reserved successfully.';
  if (path.endsWith('/equipment-requests')) return 'Equipment request submitted successfully.';
  if (method === 'DELETE') return 'Deleted successfully.';
  if (method === 'PATCH' || method === 'PUT') return 'Changes saved successfully.';
  return 'Submitted successfully.';
}

export function shouldNotify(url, options) {
  if (options.feedback === false || url.split('?')[0].endsWith('/status-refresh')) return false;
  return options.feedback === true || !['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase());
}
