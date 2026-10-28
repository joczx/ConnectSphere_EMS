import { useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import ReserveEquipment from '../components/ReserveEquipment';
import EquipmentReservations from '../components/EquipmentReservations';
export default function ReservedEquipment() {
  const [refresh, setRefresh] = useState(0);
  return <><Navbar /><main className="container">
    <div className="heading"><h1>Reserve Equipment</h1><Link to="/equipment">Review equipment requests</Link></div>
    <ReserveEquipment onReserved={() => setRefresh(value => value + 1)} refresh={refresh} />
    <EquipmentReservations refresh={refresh} onChanged={() => setRefresh(value => value + 1)} />
  </main></>;
}
