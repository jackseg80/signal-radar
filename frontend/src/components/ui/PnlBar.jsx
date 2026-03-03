export default function PnlBar({ value, maxAbs, width = 60 }) {
  if (value == null || isNaN(value) || !maxAbs) return null;

  const pct = Math.min(100, (Math.abs(value) / maxAbs) * 100);
  const isPositive = value >= 0;
  const color = isPositive ? 'var(--accent-green)' : 'var(--accent-red)';

  return (
    <div className="inline-flex items-center gap-1" style={{ width }}>
      <div className="flex-1 h-1.5 rounded-full bg-white/5 relative overflow-hidden" style={{ direction: 'rtl' }}>
        {!isPositive && (
          <div
            className="h-full rounded-full"
            style={{
              width: `${pct}%`,
              backgroundColor: color,
              opacity: 0.7,
              transition: 'width 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          />
        )}
      </div>
      <div className="w-px h-2.5 bg-[--border-subtle] shrink-0" />
      <div className="flex-1 h-1.5 rounded-full bg-white/5 relative overflow-hidden">
        {isPositive && (
          <div
            className="h-full rounded-full"
            style={{
              width: `${pct}%`,
              backgroundColor: color,
              opacity: 0.7,
              transition: 'width 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          />
        )}
      </div>
    </div>
  );
}
