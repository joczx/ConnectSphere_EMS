export const normalizeRole = role => role.trim().replaceAll('_', ' ').toLowerCase();
const coordinator = ['event coordinator'];
const technical = ['technical support staff', 'technical support'];
const venueStaff = ['venue staff'];
const safetyOfficer = ['safety officer'];
const organiser = ['event organiser', 'event organizer'];
const venueReaders = [...coordinator, ...venueStaff];
export const PAGE_ROLES = {
  '/assign-event-coordinators': ['event coordinator lead'],
  '/reassign-event-coordinators': ['event coordinator lead'],
  '/event-requests': ['event organiser', 'event organizer'],
  '/event-change-requests': ['event organiser', 'event organizer'],
  '/review-event-requests': coordinator,
  '/review-event-change-requests': coordinator,
  '/venue-bookings': coordinator,
  '/review-venue-bookings': venueStaff,
  '/equipment': technical,
  '/equipment-availability': [...coordinator, ...technical],
  '/venue-search': venueReaders,
  '/venue-suitability': coordinator,
  '/operational-safety-reviews': safetyOfficer,
  '/events': [...organiser, ...coordinator],
};
export function rolesForPath(path) {
  if (path === '/venues') return venueReaders;
  if (/^\/venues\/(new|[^/]+\/(edit|delete))$/.test(path)) return venueStaff;
  return Object.entries(PAGE_ROLES).find(([prefix]) => path === prefix || path.startsWith(prefix + '/'))?.[1] || [];
}
export function hasAccess(roles = [], required = []) {
  return required.length === 0 || roles.some(role => required.includes(normalizeRole(role)));
}
