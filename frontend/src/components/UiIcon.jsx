const paths = {
  home: 'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
  events: 'M8 3v4m8-4v4M3 10h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z',
  venues: 'M4 21V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v16M2 21h20M8 7h1m6 0h1M8 11h1m6 0h1M10 21v-6h4v6',
  equipment: 'M4 4h16v12H4zM8 20h8m-4-4v4',
  requests: 'M9 5H5v16h14V5h-4M9 3h6v4H9zM8 12h8m-8 4h5',
  search: 'M21 21l-6-6M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z',
  check: 'm5 12 4 4L19 6',
  plus: 'M12 4v16M4 12h16',
  menu: 'M4 6h16M4 12h16M4 18h16',
  bell: 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0',
};

export default function UiIcon({ name = 'requests', ...props }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d={paths[name] || paths.requests} /></svg>;
}
