export default function AccountMenu({ onSignOut }) {
  return (
    <details className="account-menu">
      <summary>Your account</summary>
      <div className="account-menu-content">
        <span>Signed in</span>
        <button type="button" className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    </details>
  );
}
