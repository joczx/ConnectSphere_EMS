import { VENUE_DAYS } from '../config/venueOptions';

export function venuePayloadFromForm(data) {
  const operatingHours = {};
  for (const [day] of VENUE_DAYS) {
    operatingHours[day] = data.has(`${day}_closed`)
      ? { closed: true }
      : { open: data.get(`${day}_open`), close: data.get(`${day}_close`) };
  }

  return {
    venue_name: data.get('venue_name'),
    capacity: Number(data.get('capacity')),
    postal_code: data.get('postal_code'),
    block_number: data.get('block_number'),
    street_name: data.get('street_name'),
    building_name: data.get('building_name') || null,
    unit_number: data.get('unit_number') || null,
    wheelchair_accessible: data.has('wheelchair_accessible'),
    blind_accessible: data.has('blind_accessible'),
    accessibility_notes: data.get('accessibility_notes') || null,
    facilities: data.getAll('facilities'),
    supported_room_layouts: data.getAll('supported_room_layouts'),
    operating_hours: operatingHours,
    default_setup_minutes: Number(data.get('default_setup_minutes')),
    default_turnaround_minutes: Number(data.get('default_turnaround_minutes')),
  };
}

function sameValue(left, right) {
  if (Array.isArray(left) || Array.isArray(right) || typeof left === 'object' || typeof right === 'object') {
    return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
  }
  return left === right;
}

export function changedVenueFields(currentVenue, values) {
  return Object.fromEntries(
    Object.entries(values).filter(([field, value]) => !sameValue(currentVenue[field], value))
  );
}
