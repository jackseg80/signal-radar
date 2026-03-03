export default function Card({ title, children, className = '', glow = '' }) {
  return (
    <div className={`glass-card rounded-xl p-5 animate-fade-in ${glow} ${className}`}>
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
