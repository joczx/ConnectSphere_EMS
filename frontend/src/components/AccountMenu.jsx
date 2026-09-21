import { useAuth } from '../auth/AuthContext';

export default function AccountMenu() {
  const { signOut } = useAuth();

  return (
    <details className="account-menu">
      <summary>Your account</summary>
      <div className="account-menu-content">
        <span>Signed in</span>
        <button type="button" className="secondary" onClick={signOut}>
          Sign out
        </button>
      </div>
    </details>
  );
}
