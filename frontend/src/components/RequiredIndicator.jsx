export default function RequiredIndicator({ required = true, title = 'Required' }) {
  return required ? <span className="required-indicator" aria-hidden="true" title={title}> *</span> : null;
}
