import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import VenueFilterForm from '../components/VenueFilterForm';
import { pageUrl } from '../services/venueSearch';

// The filters on a page of their own. The catalogue now shows the same form
// inline, so this stays for links that still point here.
export default function VenueSearchFilters() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  return (
    <>
      <Navbar />
      <main className="container">
        <Link to={pageUrl(searchParams)}>← Back to venue search</Link>
        <div className="heading">
          <div>
            <p className="eyebrow">VENUE SEARCH</p>
            <h1>Filter conditions</h1>
          </div>
        </div>
        <p>Enter the event requirements used to search for possible venues.</p>
        <div className="panel">
          <VenueFilterForm params={searchParams} onApply={(next) => navigate(pageUrl(next))} />
        </div>
      </main>
    </>
  );
}
