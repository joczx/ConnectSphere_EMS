export default function EventFormSection({ title, description, children }) {
  return <section className="event-form-section">
    <h3>{title}</h3>
    {description && <p className="metadata">{description}</p>}
    <div className="event-form-fields">{children}</div>
  </section>;
}
