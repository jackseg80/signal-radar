export default function Card({ title, children, className = '' }) {
  return (
    <div className={`bg-[--bg-card] rounded-xl border border-[--border-subtle] p-5 ${className}`}>
      {title && (
        <h2
          className="text-xs font-semibold uppercase tracking-wider text-[--text-muted] mb-4"
          style={{ fontFamily: "'Space Grotesk', sans-serif" }}
        >
          {title}
        </h2>
      )}
      {children}
    </div>
  );
}
