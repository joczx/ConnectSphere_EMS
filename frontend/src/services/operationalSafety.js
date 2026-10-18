export const safetyStatusLabel = 'Pending Safety Checks';

export function formatDateTime(value) {
  if (!value) return 'Not specified';
  return new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
  }).format(new Date(value));
}

export function present(value) {
  return value === null || value === undefined || value === '' ? 'Not recorded' : value;
}
