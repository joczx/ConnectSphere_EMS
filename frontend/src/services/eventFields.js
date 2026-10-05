// Shared between the event request form and the event information page.
//
// An event is created by copying these fields across from the approved
// request, so both pages edit the same shapes. Keeping the conversions in one
// place stops the two drifting: a change to how equipment lines are parsed has
// to hold on both sides or the same text means different things.

export const LAYOUTS = ['theatre', 'classroom', 'boardroom', 'banquet', 'exhibition', 'u_shape', 'cabaret'];
export const FACILITIES = ['stage', 'projector', 'sound_system', 'video_conferencing', 'wifi', 'parking', 'catering_area', 'air_conditioning'];

// Changing one of these may invalidate a venue booking or an equipment
// reservation already made, so the user is warned before they are saved.
// Mirrors CRITICAL_FIELDS in backend/app/schemas/event.py, which is what
// actually enforces the rule.
export const CRITICAL_FIELDS = [
  'start_datetime', 'end_datetime', 'capacity_needed', 'room_layout',
  'required_facilities', 'need_wheelchair_accessibility',
  'need_blind_accessibility', 'equipment_requirements',
];

// datetime-local inputs use the browser's local time; the API stores UTC.
export const toInput = (iso) => { if (!iso) return ''; const d = new Date(iso); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
export const toIso = (local) => {
  if (!local) return null;
  const date = new Date(local);
  return Number.isNaN(date.getTime()) ? local : date.toISOString();
};

// Equipment is edited as one "type, quantity, notes" line per item, or "none".
// Blank (null) means not answered yet.
export const toLines = (items) => !items ? '' : items.length ? items.map(i => [i.equipment_type, i.quantity, i.notes].filter(Boolean).join(', ')).join('\n') : 'none';
export const toItems = (text) => !text.trim() ? null : text.trim().toLowerCase() === 'none' ? [] : text.split('\n').filter(line => line.trim()).map(line => {
  const [equipment_type, quantity, ...notes] = line.split(',').map(part => part.trim());
  return { equipment_type, quantity: Number(quantity), notes: notes.join(', ') || null };
});

// "need_wheelchair_accessibility" -> "Need wheelchair accessibility".
// humanise() in eventRequests.js replaces only the first underscore, which is
// enough for a single-word enum value but not for a column name.
export const label = (value) => {
  const text = String(value).replaceAll('_', ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
};

// How a stored value reads on the page. Shared so the view, the warning modal
// and the activity history all describe the same value the same way.
export const display = (field, value) => {
  if (value === null || value === undefined || value === '') return 'Not specified';
  if (field.endsWith('_datetime')) return new Date(value).toLocaleString();
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (field === 'equipment_requirements') return toLines(value) || 'Not answered';
  if (Array.isArray(value)) return value.length ? value.map(label).join(', ') : 'None needed';
  return String(value);
};
