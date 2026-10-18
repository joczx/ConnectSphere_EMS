/** Shared form-to-API transformations for event change requests. */

import { toInput, toIso, toItems, toLines } from './eventFields.js';

export const PERMITTED_CHANGE_FIELDS = [
  'event_name',
  'description',
  'start_datetime',
  'end_datetime',
  'capacity_needed',
  'room_layout',
  'required_facilities',
  'need_wheelchair_accessibility',
  'need_blind_accessibility',
  'equipment_requirements',
];

export function formFromEvent(event) {
  return {
    event_name: event.event_name ?? '',
    description: event.description ?? '',
    start_datetime: toInput(event.start_datetime),
    end_datetime: toInput(event.end_datetime),
    capacity_needed: event.capacity_needed ?? '',
    room_layout: event.room_layout ?? '',
    required_facilities: event.required_facilities ?? [],
    need_wheelchair_accessibility: !!event.need_wheelchair_accessibility,
    need_blind_accessibility: !!event.need_blind_accessibility,
    equipment_requirements: toLines(event.equipment_requirements),
    reason: '',
  };
}

function saved(event, field) {
  if (field === 'equipment_requirements') return toItems(toLines(event[field]));
  if (field === 'required_facilities') return event[field] ?? [];
  if (field.startsWith('need_')) return !!event[field];
  return event[field] ?? null;
}

export function changedValues(event, form) {
  const next = {
    event_name: form.event_name.trim(),
    description: form.description.trim(),
    start_datetime: toIso(form.start_datetime),
    end_datetime: toIso(form.end_datetime),
    capacity_needed: form.capacity_needed === '' ? null : Number(form.capacity_needed),
    room_layout: form.room_layout || null,
    required_facilities: form.required_facilities,
    need_wheelchair_accessibility: form.need_wheelchair_accessibility,
    need_blind_accessibility: form.need_blind_accessibility,
    equipment_requirements: toItems(form.equipment_requirements),
  };
  return Object.fromEntries(Object.entries(next).filter(([field, value]) => {
    // Compare date inputs in the same minute-precision format shown to the
    // Organiser. Stored seconds or milliseconds are invisible in the form and
    // therefore must not become an accidental proposed change.
    if (field.endsWith('_datetime')) {
      return form[field] !== toInput(event[field]);
    }

    // Venue facilities are a set. A different array order is not a change.
    if (field === 'required_facilities') {
      const ordered = facilities => [...(facilities || [])].sort();
      return JSON.stringify(ordered(value)) !== JSON.stringify(ordered(saved(event, field)));
    }

    return JSON.stringify(value) !== JSON.stringify(saved(event, field));
  }));
}

export function reviewApi(api, path = '', options) {
  return api('/api/event-change-requests' + path, options);
}

export const statusLabel = value => value
  ? value.replaceAll('_', ' ').replace(/^./, character => character.toUpperCase())
  : '';

export const importanceLabel = value => value === 'important' ? 'Critical change' : 'Non-critical change';

export function submissionBody(event, form, confirmCritical = false) {
  return {
    reason: form.reason.trim(),
    proposed_values: changedValues(event, form),
    expected_event_updated_at: event.updated_at,
    confirm_critical: confirmCritical,
  };
}

