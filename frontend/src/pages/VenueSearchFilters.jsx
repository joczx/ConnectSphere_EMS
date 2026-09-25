import { useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { Alert, AlertDescription, AlertTitle } from '../components/Alert';
import DateRangePicker from '../components/DateRangePicker';
import { VENUE_FACILITIES, VENUE_ROOM_LAYOUTS } from '../config/venueOptions';

function dateValue(value) {
  const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(value);
  if (!match) return null;
  const [, day, month, year] = match;
  const date = new Date(`${year}-${month}-${day}T00:00:00`);
  if (date.getFullYear() !== Number(year) || date.getMonth() !== Number(month) - 1 || date.getDate() !== Number(day)) return null;
  return `${year}-${month}-${day}`;
}

export default function VenueSearchFilters() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [issues, setIssues] = useState([]);
  const [dates, setDates] = useState(() => ({
    startDate: searchParams.get('start_date') || '',
    endDate: searchParams.get('end_date') || '',
  }));
  const [calendarKey, setCalendarKey] = useState(0);
  const alertRef = useRef(null);

  function showIssues(nextIssues) {
    setIssues(nextIssues);
    requestAnimationFrame(() => {
      alertRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      alertRef.current?.focus();
    });
  }

  function showResults(event) {
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
    const parameters = new URLSearchParams({ filter: 'true' });
    for (const [name, value] of formData) {
      if (value) parameters.append(name, value);
    }
    if (startDate) parameters.append('start_date', startDate);
    if (endDate) parameters.append('end_date', endDate);
    navigate('/venue-search/results?' + parameters.toString());
  }

  return (
    <>
      <Navbar />
      <main className="container">
        <Link to="/venue-search">← Back to venue search</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE SEARCH</p>
            <h1>Filter conditions</h1>
          </div>
        </div>
        <p>Enter the event requirements used to search for possible venues.</p>

        <form className="panel search-filter-form" noValidate onReset={() => {
          setDates({ startDate: '', endDate: '' });
          setCalendarKey(key => key + 1);
          setIssues([]);
        }} onSubmit={showResults}>
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
                <input name="capacity" type="number" defaultValue={searchParams.get('capacity') || ''} placeholder="Number of attendees" onChange={() => setIssues([])} />
              </label>
              <label>
                Location
                <input name="location" type="search" defaultValue={searchParams.get('location') || ''} placeholder="Venue, building, street or postal code" />
              </label>
            </div>
            <div className="layout-options">
              <p className="filter-label">Acceptable room layouts</p>
              <p className="filter-help">Select one or more layouts.</p>
              <div className="facility-options">
                {VENUE_ROOM_LAYOUTS.map(([value, label]) => (
                  <label className="facility-option" key={value}>
                    <input name="layouts" type="checkbox" value={value} defaultChecked={searchParams.getAll('layouts').includes(value)} />
                    {label}
                  </label>
                ))}
              </div>
            </div>
          </fieldset>

          <fieldset>
            <legend>Accessibility</legend>
            <div className="search-filter-grid">
              <label>
                Wheelchair accessibility
                <select name="wheelchair_accessible" defaultValue={searchParams.get('wheelchair_accessible') || ''}>
                  <option value="">Any</option>
                  <option value="true">Required</option>
                </select>
              </label>
              <label>
                Blind accessibility
                <select name="blind_accessible" defaultValue={searchParams.get('blind_accessible') || ''}>
                  <option value="">Any</option>
                  <option value="true">Required</option>
                </select>
              </label>
            </div>
          </fieldset>

          <fieldset>
            <legend>Required facilities</legend>
            <div className="facility-options">
              {VENUE_FACILITIES.map(([value, label]) => (
                <label className="facility-option" key={value}>
                  <input name="facilities" type="checkbox" value={value} defaultChecked={searchParams.getAll('facilities').includes(value)} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="search-filter-actions">
            <button type="submit">Search venues</button>
            <button type="reset" className="secondary">Clear all</button>
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
      </main>
    </>
  );
}
