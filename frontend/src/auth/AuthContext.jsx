import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { hasAccess, rolesForPath } from './access';
import { readApiResponse } from '../services/http';
import { useFeedback } from '../components/FeedbackProvider';
import { actionMessage, shouldNotify } from '../services/actionFeedback';

const AuthContext = createContext(null);

function storedSession() {
  try {
    const savedSession = sessionStorage.getItem('auth_session');
    if (savedSession) return JSON.parse(savedSession);
    const legacyToken = sessionStorage.getItem('access_token');
    return legacyToken ? { access_token: legacyToken } : null;
  } catch {
    sessionStorage.removeItem('auth_session');
    return null;
  }
}

export function AuthProvider({ children }) {
  const { notify } = useFeedback();
  const [session, setSession] = useState(storedSession);
  const sessionRef = useRef(session);
  const refreshPromiseRef = useRef(null);

  const saveSession = useCallback((nextSession) => {
    sessionRef.current = nextSession;
    setSession(nextSession);
    if (nextSession) sessionStorage.setItem('auth_session', JSON.stringify(nextSession));
    else sessionStorage.removeItem('auth_session');
    sessionStorage.removeItem('access_token');
  }, []);

  const signOut = useCallback(() => saveSession(null), [saveSession]);

  const refreshSession = useCallback(async () => {
    if (refreshPromiseRef.current) return refreshPromiseRef.current;

    const refreshToken = sessionRef.current?.refresh_token;
    if (!refreshToken) {
      signOut();
      return null;
    }

    refreshPromiseRef.current = (async () => {
      try {
        const response = await fetch('/api/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        const nextSession = await readApiResponse(response);
        saveSession(nextSession);
        return nextSession.access_token;
      } catch {
        signOut();
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    return refreshPromiseRef.current;
  }, [saveSession, signOut]);

  const authFetch = useCallback(async (url, options = {}) => {
    const send = (accessToken) => {
      const headers = new Headers(options.headers);
      headers.set('Authorization', `Bearer ${accessToken}`);
      return fetch(url, { ...options, headers });
    };

    const accessToken = sessionRef.current?.access_token;
    if (!accessToken) {
      signOut();
      throw new Error('Your session has expired. Please sign in again.');
    }

    let response = await send(accessToken);
    if (response.status !== 401) return response;

    const refreshedAccessToken = await refreshSession();
    if (!refreshedAccessToken) throw new Error('Your session has expired. Please sign in again.');

    response = await send(refreshedAccessToken);
    if (response.status === 401) signOut();
    return response;
  }, [refreshSession, signOut]);

  const api = useCallback(async (url, options = {}) => {
    const { body, headers: suppliedHeaders, feedback, successFeedback, successMessage, ...rest } = options;
    const headers = new Headers(suppliedHeaders);
    let requestBody = body;

    if (
      body !== undefined && body !== null && typeof body !== 'string'
      && !(body instanceof FormData) && !(body instanceof URLSearchParams)
      && !(body instanceof Blob)
    ) {
      headers.set('Content-Type', 'application/json');
      requestBody = JSON.stringify(body);
    }

    try {
      const response = await authFetch(url, {
        ...rest,
        headers,
        ...(body !== undefined ? { body: requestBody } : {}),
      });
      const data = await readApiResponse(response);
      if (shouldNotify(url, options) && successFeedback !== false && !options.signal?.aborted) {
        const message = typeof successMessage === 'function' ? successMessage(data)
          : successMessage || actionMessage(url, (options.method || 'GET').toUpperCase(), data);
        notify(message);
      }
      return data;
    } catch (error) {
      if (shouldNotify(url, options) && !options.signal?.aborted && error.name !== 'AbortError' && !error.data?.critical_fields) {
        notify(error.message || 'Unable to complete this action. Please try again.', 'error');
      }
      throw error;
    }
  }, [authFetch, notify]);

  const [account, setAccount] = useState({ user: null, loading: true, error: '' });
  const accountId = session?.user?.id || session?.access_token;
  useEffect(() => {
    const controller = new AbortController();
    setAccount({ user: null, loading: !!accountId, error: '', accountId });
    if (accountId) api('/api/users/me', { cache: 'no-store', signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setAccount({ user: data.user, loading: false, error: '', accountId }); })
      .catch(error => { if (!controller.signal.aborted) setAccount({ user: null, loading: false, error: error.message, accountId }); });
    return () => controller.abort();
  }, [api, accountId]);
  const accountReady = account.accountId === accountId && !account.loading;
  const canAccess = useCallback(path => accountReady && !account.error && hasAccess(account.user?.roles, rolesForPath(path)), [account, accountReady]);

  const value = useMemo(() => ({
    session,
    token: session?.access_token ?? null,
    signIn: saveSession,
    signOut,
    authFetch,
    api,
    account,
    accountReady,
    canAccess,
  }), [session, saveSession, signOut, authFetch, api, account, accountReady, canAccess]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
