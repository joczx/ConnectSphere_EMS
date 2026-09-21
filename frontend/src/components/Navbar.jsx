import AccountMenu from './AccountMenu';
import { Link } from 'react-router-dom';

export default function Navbar({ onSignOut, searchBar }) {
  return (
    <header className={'home-navbar' + (searchBar ? ' home-navbar-search' : '')}>
      <Link className="brand" to="/home">ConnectSphere</Link>
      {searchBar}
      <AccountMenu onSignOut={onSignOut} />
    </header>
  );
}
