import AccountMenu from './AccountMenu';
import { Link } from 'react-router-dom';

export default function Navbar({ searchBar }) {
  return (
    <header className={'home-navbar' + (searchBar ? ' home-navbar-search' : '')}>
      <Link className="portal-title" to="/home">Event Management Portal</Link>
      {searchBar}
      <AccountMenu />
    </header>
  );
}
