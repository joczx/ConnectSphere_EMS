// The venue search filter conditions, as a form.
//
// Used inline on the venue catalogue and on its own on the Filters page, so
// both write the URL the same way. It starts from whatever the URL already
// says, so it is remounted (keyed on the URL) whenever a filter changes
// elsewhere, such as a chip being removed.

import { useRef, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from './Alert';
import DateRangePicker from './DateRangePicker';
import { VENUE_FACILITIES, VENUE_ROOM_LAYOUTS } from '../config/venueOptions';
import { APPLIED_KEY, EVENT_KEY, withoutFilters } from '../services/venueSearch';

function dateValue(value) {
  const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(value);
  if (!match) return null;
  const [, day, month, year] = match;
  const date = new Date(`${year}-${month}-${day}T00:00:00`);
  if (date.getFullYear() !== Number(year) || date.getMonth() !== Number(month) - 1 || date.getDate() !== Number(day)) return null;
  return `${year}-${month}-${day}`;
}

export default function VenueFilterForm({ params, onApply, onCancel }) {
  const [issues, setIssues] = useState([]);
  const [dates, setDates] = useState(() => ({
    startDate: params.get('start_date') || '',
    endDate: params.get('end_date') || '',
  }));
  const [calendarKey, setCalendarKey] = useState(0);
  const alertRef = useRef(null);
  const formRef = useRef(null);
  const eventId = params.get(EVENT_KEY) || '';

  // Not a form reset: a reset returns each field to its default, and the
  // defaults are the filters already in force, so it would clear nothing the
  // coordinator arrived with.
  function untickEverything() {
    for (const field of formRef.current.elements) {
      if (field.type === 'checkbox') field.checked = false;
      else if (field.name) field.value = '';
    }
    setDates({ startDate: '', endDate: '' });
    setCalendarKey(key => key + 1);
    setIssues([]);
  }

  function showIssues(nextIssues) {
    setIssues(nextIssues);
    requestAnimationFrame(() => {
      alertRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      alertRef.current?.focus();
    });
  }

  function apply(event) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const { startDate, endDate } = dates;
    const capacity = formData.get('capacity');
    const nextIssues = [];

    if ((startDate || endDate) && !(startDate && endDate)) {
      nextIssues.push({ category: 'dates', message: 'Enter both event start and end dates.' });
    }
    const start = dateValue(startDate);
    const end = dateValue(endDate);
    if (startDate && endDate && (!start || !end)) {
      nextIssues.push({ category: 'dates', message: 'Use DD-MM-YYYY for event start and end dates.' });
    }
    if (start && end && end < start) {
      nextIssues.push({ category: 'dates', message: 'Event end date cannot be before the start date.' });
    }
    if (capacity && (!Number.isInteger(Number(capacity)) || Number(capacity) < 1)) {
      nextIssues.push({ category: 'requirements', message: 'Expected attendance must be a positive whole number.' });
    }
    if (nextIssues.length) {
      showIssues(nextIssues);
      return;
    }

    setIssues([]);
    // Everything that is not a filter condition survives: the event being
    // planned, and the name typed into the search bar, which this form does
    // not show and so must not silently drop.
    const parameters = withoutFilters(params);
    if (params.get('name')) parameters.set('name', params.get('name'));
    // `applied` tells the catalogue the coordinator has now chosen the filters
    // themselves, so the event's own requirements are not put back over them.
    if (eventId) parameters.set(APPLIED_KEY, '1');
    for (const [name, value] of formData) {
      if (value) parameters.append(name, value);
    }
    if (startDate) parameters.set('start_date', startDate);
    if (endDate) parameters.set('end_date', endDate);
    onApply(parameters);
  }

  return (
    <form className="search-filter-form" noValidate ref={formRef} onSubmit={apply}>
      {eventId && (
        <p className="metadata">
          These conditions start from what event #{eventId} needs. Widening or clearing them
          shows more venues, but one that cannot meet the event’s requirements still cannot be
          requested for it.
        </p>
      )}

      <fieldset>
        <legend>Available dates {issues.some(issue => issue.category === 'dates') && <span className="error-marker">*</span>}</legend>
        <DateRangePicker key={calendarKey} value={dates} onChange={(nextDates) => {
          setDates(nextDates);
          setIssues([]);
        }} />
      </fieldset>

      <fieldset>
        <legend>Venue requirements {issues.some(issue => issue.category === 'requirements') && <span className="error-marker">*</span>}</legend>
        <div className="search-filter-grid">
          <label>
            Expected attendance
            <input name="capacity" type="number" defaultValue={params.get('capacity') || ''} placeholder="Number of attendees" onChange={() => setIssues([])} />
          </label>
          <label>
            Location
            <input name="location" type="search" defaultValue={params.get('location') || ''} placeholder="Venue, building, street or postal code" />
          </label>
        </div>
        <div className="layout-options">
          <p className="filter-label">Acceptable room layouts</p>
          <p className="filter-help">Select one or more layouts.</p>
          <div className="facility-options">
            {VENUE_ROOM_LAYOUTS.map(([value, label]) => (
              <label className="facility-option" key={value}>
                <input name="layouts" type="checkbox" value={value} defaultChecked={params.getAll('layouts').includes(value)} />
                {label}
              </label>
            ))}
          </div>
        </div>
      </fieldset>

      {/* Tickboxes rather than Any / Required menus: each is a condition that is
          either on or off, like every other filter here. An unticked box sends
          nothing, which the search reads as "any". */}
      <fieldset>
        <legend>Accessibility</legend>
        <div className="facility-options">
          <label className="facility-option">
            <input name="wheelchair_accessible" type="checkbox" value="true" defaultChecked={params.get('wheelchair_accessible') === 'true'} />
            Wheelchair accessible
          </label>
          <label className="facility-option">
            <input name="blind_accessible" type="checkbox" value="true" defaultChecked={params.get('blind_accessible') === 'true'} />
            Accessible for blind attendees
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Required facilities</legend>
        <div className="facility-options">
          {VENUE_FACILITIES.map(([value, label]) => (
            <label className="facility-option" key={value}>
              <input name="facilities" type="checkbox" value={value} defaultChecked={params.getAll('facilities').includes(value)} />
              {label}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="search-filter-actions">
        <button type="submit">Apply filters</button>
        <button type="button" className="secondary" onClick={untickEverything}>Untick everything</button>
        {onCancel && <button type="button" className="secondary" onClick={onCancel}>Cancel</button>}
      </div>
      {issues.length > 0 && <div className="page-alert" ref={alertRef} tabIndex="-1">
        <Alert variant="destructive">
          <AlertTitle>Unable to process your search conditions.</AlertTitle>
          <AlertDescription>
            <p>Please verify your filter conditions and try again.</p>
            <ul>{issues.map(issue => <li key={issue.message}>{issue.message}</li>)}</ul>
          </AlertDescription>
        </Alert>
      </div>}
    </form>
  );
}
