// Shared by the coordinator's Venue Bookings page and the Venue Staff review
// pages, so both describe a request and its status the same way.

export const venueBookingsApi = (api, path = '', options) => (
  api('/api/venue-bookings' + path, { cache: 'no-store', ...options })
);

export const STATUS_LABELS = {
  submitted: 'Awaiting review',
  approved: 'Approved',
  rejected: 'Rejected',
};

export const statusLabel = (status) => STATUS_LABELS[status] || status || 'Unknown';

export const when = (iso) => iso
  ? new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
  }).format(new Date(iso))
  : 'Not specified';

// A booking's period in one phrase. formatRange drops whatever the two ends
// share, so a same-day event reads "31 Oct 2026, 6:35 – 11:35 pm" rather than
// repeating the date.
const PERIOD = new Intl.DateTimeFormat('en-SG', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Singapore',
});
export const period = (start, end) => {
  if (!start || !end) return 'Not specified';
  try {
    return PERIOD.formatRange(new Date(start), new Date(end));
  } catch {
    return `${when(start)} – ${when(end)}`;
  }
};

// Requests grouped by where they are in review, newest first within each.
export const byStatus = (bookings, status) => (bookings || []).filter(item => item.status === status);
