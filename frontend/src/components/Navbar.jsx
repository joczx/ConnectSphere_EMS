import AccountMenu from './AccountMenu';
import { Link } from 'react-router-dom';

export default function Navbar({ onSignOut }) {
  return (
    <header className="home-navbar">
      <Link className="brand" to="/home">ConnectSphere</Link>
      <AccountMenu onSignOut={onSignOut} />
    </header>
  );
}
