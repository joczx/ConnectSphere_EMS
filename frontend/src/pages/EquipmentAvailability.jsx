import { readApiResponse } from '../services/http';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';

const formatDateTime = (value) => {
  if (!value) return 'Not specified';
  return new Intl.DateTimeFormat('en-SG', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Singapore',
  }).format(new Date(value));
};

export default function EquipmentAvailability({ token, onSignOut }) {
  const [form, setForm] = useState({
    equipment_type: '',
    quantity: 1,
    start_datetime: '',
    end_datetime: '',
  });
  const [state, setState] = useState({ loading: false, results: [], message: '', error: '' });

  const [equipmentTypes, setEquipmentTypes] = useState([]);

  useEffect(() => {
    let ignore = false;
    fetch('/api/equipment-types', {
      headers: { Authorization: 'Bearer ' + token },
      cache: 'no-store',
    })
      .then(readApiResponse)
      .then(data => { if (!ignore) setEquipmentTypes(data.equipment_types || []); })
      .catch(err => { if (!ignore) setState(previous => ({ ...previous, error: err.message })); });
    return () => { ignore = true; };
  }, [token]);

  async function searchAvailability(event) {
    event.preventDefault();
    setState({ loading: true, results: [], message: '', error: '' });

    try {
      const params = new URLSearchParams({
        equipment_type: form.equipment_type,
        quantity: String(Number(form.quantity) || 0),
        start_datetime: new Date(form.start_datetime).toISOString(),
        end_datetime: new Date(form.end_datetime).toISOString(),
      });

      const response = await fetch(`/api/equipment-availability?${params.toString()}`, {
        headers: { Authorization: 'Bearer ' + token },
        cache: 'no-store',
      });
      const data = await readApiResponse(response);
      if (!response.ok) throw new Error(data.error || 'Unable to check equipment availability.');

      setState({
        loading: false,
        results: data.results || [],
        message: data.message || '',
        error: '',
      });
    } catch (err) {
      setState({ loading: false, results: [], message: '', error: err.message || 'Unable to check equipment availability.' });
    }
  }

  return (
    <>
      <Navbar onSignOut={onSignOut} />
      <main className="container">
        {/* <Link to="/home">← Home</Link> */}
        <div className="heading">
          <div>
            <p className="eyebrow">TECHNICAL SUPPORT</p>
            <h1>Check equipment availability</h1>
          </div>
        </div>

        <form className="panel" onSubmit={searchAvailability} style={{ display: 'grid', gap: '12px' }}>
          <label>
            Equipment type
            {/* <input
              value={form.equipment_type}
              onChange={(e) => setForm({ ...form, equipment_type: e.target.value })}
              placeholder="Projector"
              required
            /> */}
            <select value={form.equipment_type} onChange={(e) => setForm({ ...form, equipment_type: e.target.value })} required>
                <option value="">Select</option>
                {equipmentTypes.map(type => <option key={type} value={type}>{type}</option>)}
                </select>
          </label>

          <label>
            Requested quantity
            <input
              type="number"
              min="1"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              required
            />
          </label>

          <label>
            Required start date and time
            <input
              type="datetime-local"
              value={form.start_datetime}
              onChange={(e) => setForm({ ...form, start_datetime: e.target.value })}
              required
            />
          </label>

          <label>
            Required end date and time
            <input
              type="datetime-local"
              value={form.end_datetime}
              onChange={(e) => setForm({ ...form, end_datetime: e.target.value })}
              required
            />
          </label>

          <button type="submit" disabled={state.loading}>
            {state.loading ? 'Checking…' : 'Check availability'}
          </button>
        </form>

        {state.error && <div role="alert" className="panel error">{state.error}</div>}

        {state.message && state.results.length === 0 && <div className="panel" style={{ marginTop: '24px' }}>{state.message}</div>}

        {state.results.length > 0 && (
          <section className="panel" style={{ marginTop: '24px' }}>
            <h2>Availability results</h2>
            {state.results.map((item) => (
              <div key={`${item.equipment_id}-${item.equipment_model}`} className="panel" style={{ marginTop: '12px' }}>
                <h3>{item.equipment_type} — {item.equipment_model}</h3>
                <p>Available quantity: {item.available_quantity}</p>
                <p>Requested quantity: {item.requested_quantity}</p>
                <p>Required period: {formatDateTime(item.required_start)} to {formatDateTime(item.required_end)}</p>
                <p>Fulfillment status: {item.fulfillment_status === 'available' ? 'Available' : 'Partially available'}</p>
              </div>
            ))}
          </section>
        )}
      </main>
    </>
  );
}
