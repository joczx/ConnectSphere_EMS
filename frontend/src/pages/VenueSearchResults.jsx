import { Navigate, useSearchParams } from 'react-router-dom';

// Results used to live on their own page, reached from the filter form and the
// name search. The catalogue page now lists them beside the filters that
// produced them and the event they are being searched for, so there is one
// results surface rather than two that could disagree.
//
// The route is kept so that a bookmarked or shared result still opens, with
// every filter in the URL carried across.
export default function VenueSearchResults() {
  const [params] = useSearchParams();
  const carried = new URLSearchParams(params);
  // Only ever meant "these are filter results", which the filters in the URL
  // now say for themselves.
  carried.delete('filter');
  const suffix = carried.toString();
  return <Navigate replace to={suffix ? `/venue-search?${suffix}` : '/venue-search'} />;
}
