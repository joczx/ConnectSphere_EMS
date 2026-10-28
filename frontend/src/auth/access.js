export const normalizeRole = role => role.trim().replaceAll('_', ' ').toLowerCase();
const organiser = ['event organiser', 'event organizer'];
const coordinator = ['event coordinator'];
const lead = ['event coordinator lead'];
const technical = ['technical support staff', 'technical support'];
const venueStaff = ['venue staff'];
const safetyOfficer = ['safety officer'];

// Who may open each page. A path matches its own entry and everything below
// it, so '/venues' also covers '/venues/:id'. A path with no entry is open to
// every signed-in user.
export const PAGE_ROLES = {
  '/event-registration': ['attendee'],
  '/assign-event-coordinators': lead,
  '/reassign-event-coordinators': lead,
  '/event-requests': organiser,
  '/event-change-requests': organiser,
  '/review-event-requests': coordinator,
  '/review-event-change-requests': coordinator,
  '/venue-bookings': coordinator,
  '/review-venue-bookings': venueStaff,
  '/venues': [...coordinator, ...venueStaff],
  '/equipment': technical,
  '/equipment-requests': coordinator,
  '/reserved-equipment': technical,
  '/equipment-availability': [...coordinator, ...technical],
  '/venue-search': coordinator,
  '/venue-suitability': coordinator,
  '/operational-safety-reviews': safetyOfficer,
};
export function rolesForPath(path) {
  if (/^\/venues\/(new|[^/]+\/(edit|delete))$/.test(path)) return venueStaff;
  return Object.entries(PAGE_ROLES).find(([prefix]) => path === prefix || path.startsWith(prefix + '/'))?.[1] || [];
}
export function hasAccess(roles = [], required = []) {
  return required.length === 0 || roles.some(role => required.includes(normalizeRole(role)));
}

// How a user can be linked to an event or event request, by the column that
// names them. safety_officer_id is filled on approval (043).
const RELATION_FIELDS = {
  organiser: 'event_organiser_id',
  coordinator: 'event_coordinator_id',
  technical: 'technical_support_id',
  venueStaff: 'venue_staff_id',
  safety: 'safety_officer_id',
};

// Who may see each action's button. `roles`: the user must hold one of them.
// `relation`: when the page passes the record, the user must also be linked
// to it in one of these ways. Status rules (only while planning, only while
// pending) depend on the record, not the user, and stay in the page.
export const ACTIONS = {
  'event.create': { roles: organiser },
  'event.edit': { roles: coordinator, relation: ['coordinator'] },
  'event.cancel': { roles: coordinator, relation: ['coordinator'] },
  'event.registrationReady': { roles: coordinator, relation: ['coordinator'] },
  'event.registrationPeriod': { roles: organiser, relation: ['organiser'] },
  'event.findVenue': { roles: coordinator, relation: ['coordinator'] },
  'event.submitSafety': { roles: coordinator, relation: ['coordinator'] },

  'eventRequest.delete': { roles: organiser, relation: ['organiser'] },
  'eventRequest.cancel': { roles: organiser, relation: ['organiser'] },
  'eventRequest.review': { roles: coordinator, relation: ['coordinator'] },
  'eventRequest.assign': { roles: lead },
  'eventRequest.reassign': { roles: lead },

  'changeRequest.create': { roles: organiser, relation: ['organiser'] },
  'changeRequest.review': { roles: coordinator, relation: ['coordinator'] },

  'booking.request': { roles: coordinator },
  'booking.cancel': { roles: coordinator },
  'booking.review': { roles: venueStaff, relation: ['venueStaff'] },
  'booking.hold': { roles: venueStaff, relation: ['venueStaff'] },
  'booking.releaseHold': { roles: venueStaff, relation: ['venueStaff'] },

  'venue.create': { roles: venueStaff },
  'venue.edit': { roles: venueStaff },
  'venue.delete': { roles: venueStaff },
  'venue.block': { roles: venueStaff },
  'venue.unblock': { roles: venueStaff },
  'venue.viewCalendar': { roles: [...coordinator, ...venueStaff] },

  'safety.decide': { roles: safetyOfficer, relation: ['safety'] },

  'equipment.request': { roles: coordinator, relation: ['coordinator'] },
  'equipment.review': { roles: technical, relation: ['technical'] },
  'equipment.reserve': { roles: technical, relation: ['technical'] },
  'equipment.manageReservation': { roles: technical },
};

// Which events a user sees: the ones they are linked to as organiser,
// coordinator, technical support, venue staff or safety officer. An Event Coordinator Lead
// sees every event.
export function canViewEvent(roles, userId, event) {
  if (!event) return false;
  if (hasAccess(roles, lead)) return true;
  return !!userId && Object.values(RELATION_FIELDS).some(field => event[field] === userId);
}

// Lists the database already narrows to the user's own rows may leave out
// `record`; only the role is checked then.
export function can(roles, userId, action, record) {
  const rule = ACTIONS[action];
  if (!rule || !hasAccess(roles, rule.roles)) return false;
  if (!rule.relation || record === undefined) return true;
  return !!record && !!userId
    && rule.relation.some(relation => record[RELATION_FIELDS[relation]] === userId);
}
