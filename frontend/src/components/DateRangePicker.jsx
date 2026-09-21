import { useState } from 'react';
import DateRangeCalendar from './DateRangeCalendar';

export default function DateRangePicker({ value, onChange }) {
  const [isOpen, setIsOpen] = useState(false);

  function updateDate(name, nextValue) {
    const digits = nextValue.replace(/\D/g, '').slice(0, 8);
    const formatted = digits.replace(/^(\d{2})(\d)/, '$1-$2').replace(/^(\d{2}-\d{2})(\d)/, '$1-$2');
    onChange({ ...value, [name]: formatted });
  }

  return (
    <div className="date-range-picker" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setIsOpen(false);
    }}>
      <div className="date-range-values">
        <label className="date-range-value">
          Start date
          <input aria-expanded={isOpen} inputMode="numeric" maxLength="10" onChange={(event) => updateDate('startDate', event.target.value)} onFocus={() => setIsOpen(true)} pattern="\d{2}-\d{2}-\d{4}" placeholder="DD-MM-YYYY" type="text" value={value.startDate} />
        </label>
        <label className="date-range-value">
          End date
          <input aria-expanded={isOpen} inputMode="numeric" maxLength="10" onChange={(event) => updateDate('endDate', event.target.value)} onFocus={() => setIsOpen(true)} pattern="\d{2}-\d{2}-\d{4}" placeholder="DD-MM-YYYY" type="text" value={value.endDate} />
        </label>
      </div>
      {isOpen && <div className="date-range-popover" role="dialog" aria-label="Choose available dates">
        <DateRangeCalendar onStartChange={(startDate) => onChange({ ...value, startDate })} onChange={(nextDates) => {
          onChange(nextDates);
          setIsOpen(false);
        }} />
      </div>}
    </div>
  );
}
