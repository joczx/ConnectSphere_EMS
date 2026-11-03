import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

const FeedbackContext = createContext(null);

export function FeedbackProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [questions, setQuestions] = useState([]);
  const sequence = useRef(0);
  const timers = useRef(new Map());
  const pending = useRef(new Map());
  const recent = useRef({});
  const dialog = useRef(null);
  const active = questions[0];

  const dismiss = useCallback(id => {
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setMessages(current => current.filter(message => message.id !== id));
  }, []);

  const notify = useCallback((message, variant = 'success', title) => {
    if (!message) return;
    const key = `${variant}:${message}`;
    if (recent.current[key] && Date.now() - recent.current[key] < 1500) return;
    recent.current = { [key]: Date.now() };
    const id = ++sequence.current;
    setMessages(current => [...current.slice(-4), { id, message, variant,
      title: title || (variant === 'error' ? 'Action could not be completed' : variant === 'info' ? 'Please note' : 'Action completed') }]);
    if (variant !== 'error') timers.current.set(id, setTimeout(() => dismiss(id), 6000));
  }, [dismiss]);

  const confirm = useCallback((message, options = {}) => new Promise(resolve => {
    const id = ++sequence.current;
    pending.current.set(id, resolve);
    setQuestions(current => [...current, { id, message, ...options }]);
  }), []);

  const answer = useCallback((id, accepted) => {
    if (dialog.current?.open) dialog.current.close();
    pending.current.get(id)?.(accepted);
    pending.current.delete(id);
    setQuestions(current => current.filter(question => question.id !== id));
  }, []);

  useEffect(() => {
    if (!active) return;
    const node = dialog.current;
    node.showModal();
    return () => node.close();
  }, [active]);

  useEffect(() => () => {
    timers.current.forEach(clearTimeout);
    timers.current.clear();
    pending.current.forEach(resolve => resolve(false));
    pending.current.clear();
  }, []);

  return <FeedbackContext.Provider value={{ notify, confirm }}>
    <div className="feedback-app" onInvalidCapture={() => notify('Check the highlighted fields and complete all required information before continuing.', 'error', 'Check your information')}>
      {children}
    </div>
    <div className="feedback-stack" aria-label="Action notifications">
      {messages.map(item => <div key={item.id} className={`feedback-toast feedback-${item.variant}`}
        role={item.variant === 'error' ? 'alert' : 'status'} aria-atomic="true">
        <span className="feedback-symbol" aria-hidden="true">{item.variant === 'error' ? '!' : item.variant === 'info' ? 'i' : '✓'}</span>
        <div><strong>{item.title}</strong><p>{item.message}</p></div>
        <button type="button" className="feedback-dismiss" aria-label="Dismiss notification" onClick={() => dismiss(item.id)}>×</button>
      </div>)}
    </div>
    {active && <dialog ref={dialog} className="feedback-dialog" aria-labelledby="feedback-dialog-title" aria-describedby="feedback-dialog-description"
      onCancel={event => { event.preventDefault(); answer(active.id, false); }}>
      <h2 id="feedback-dialog-title">{active.title || 'Confirm action'}</h2>
      <p id="feedback-dialog-description">{active.message}</p>
      <div className="feedback-actions">
        <button type="button" className="secondary" autoFocus onClick={() => answer(active.id, false)}>{active.cancelLabel || 'Go back'}</button>
        <button type="button" className={active.destructive ? 'feedback-danger' : ''} onClick={() => answer(active.id, true)}>{active.confirmLabel || 'Confirm'}</button>
      </div>
    </dialog>}
  </FeedbackContext.Provider>;
}

export function useFeedback() {
  const context = useContext(FeedbackContext);
  if (!context) throw new Error('useFeedback must be used inside FeedbackProvider');
  return context;
}
