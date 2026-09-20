import { useRef } from 'react';
import {
  Button,
  CalendarCell,
  CalendarGrid,
  CalendarGridBody,
  CalendarGridHeader,
  CalendarHeaderCell,
  Heading,
  RangeCalendar,
} from 'react-aria-components';

function formatDate(date) {
  const [year, month, day] = date.toString().split('-');
  return `${day}-${month}-${year}`;
}

export default function DateRangeCalendar({ onChange, onStartChange }) {
  const startDate = useRef(null);

  function selectStart(date) {
    if (startDate.current) return;
    startDate.current = date;
    onStartChange(formatDate(date));
  }

  function selectRange(nextRange) {
    if (!nextRange?.start || !nextRange.end) return;
    startDate.current = null;
    onChange({
      startDate: formatDate(nextRange.start),
      endDate: formatDate(nextRange.end),
    });
  }

  return (
    <RangeCalendar aria-label="Available dates" className="date-range-calendar" onChange={selectRange}>
      <header className="date-range-calendar-header">
        <Button slot="previous" aria-label="Previous month">‹</Button>
        <Heading />
        <Button slot="next" aria-label="Next month">›</Button>
      </header>
      <CalendarGrid className="date-range-calendar-grid">
        <CalendarGridHeader>{(day) => <CalendarHeaderCell>{day}</CalendarHeaderCell>}</CalendarGridHeader>
        <CalendarGridBody>{(date) => <CalendarCell className="date-range-day" date={date} onClick={() => selectStart(date)} onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') selectStart(date);
        }} />}</CalendarGridBody>
      </CalendarGrid>
    </RangeCalendar>
  );
}
