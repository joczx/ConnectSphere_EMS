import { useAuth } from '../auth/AuthContext';
import { useFeedback } from './FeedbackProvider';

export default function AccountMenu() {
  const { notify } = useFeedback();
  const { account, signOut } = useAuth();

  return (
    <details className="account-menu">
      <summary>
        <span>{account.user?.name}</span>
        {account.user?.roles?.length > 0 && (
          <span className="account-menu-roles">{account.user.roles.join(', ')}</span>
        )}
      </summary>
      <div className="account-menu-content">
        <span>Signed in</span>
        {account.error && <span role="status">{account.error}</span>}
        <button type="button" className="secondary" onClick={() => { signOut(); notify('You have been signed out.', 'success', 'Signed out'); }}>
          Sign out
        </button>
      </div>
    </details>
  );
}
