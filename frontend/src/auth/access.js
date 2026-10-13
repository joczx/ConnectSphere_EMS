export const normalizeRole = role => role.trim().replaceAll('_', ' ').toLowerCase();
const coordinator = ['event coordinator'];
const technical = ['technical support staff', 'technical support'];
const venueStaff = ['venue staff'];
export const PAGE_ROLES = {
  '/assign-event-coordinators': ['event coordinator lead'],
  '/reassign-event-coordinators': ['event coordinator lead'],
  '/event-requests': ['event organiser', 'event organizer'],
  '/review-event-requests': coordinator,
  '/venue-bookings': coordinator,
  '/review-venue-bookings': venueStaff,
  '/equipment': technical,
  '/equipment-availability': [...coordinator, ...technical],
  '/venue-search': coordinator,
  '/venue-suitability': coordinator,
};
export function rolesForPath(path) {
  if (/^\/venues\/(new|[^/]+\/(edit|delete))$/.test(path)) return venueStaff;
  return Object.entries(PAGE_ROLES).find(([prefix]) => path === prefix || path.startsWith(prefix + '/'))?.[1] || [];
}
export function hasAccess(roles = [], required = []) {
  return required.length === 0 || roles.some(role => required.includes(normalizeRole(role)));
}
