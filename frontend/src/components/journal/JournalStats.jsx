import { formatPnl, pnlColor } from '../../utils/format';

export default function JournalStats({ stats }) {
  if (!stats) return null;

  const items = [
    { label: 'Total', value: stats.total_trades },
    { label: 'Open', value: stats.open_trades },
    {
      label: 'Win Rate',
      value: stats.closed_trades > 0 ? `${stats.win_rate}%` : '--',
      color:
        stats.win_rate >= 55
          ? 'text-green-400'
          : stats.win_rate >= 45
            ? 'text-amber-400'
            : stats.win_rate > 0
              ? 'text-red-400'
              : '',
    },
    {
      label: 'Net PnL',
      value: formatPnl(stats.total_pnl),
      color: pnlColor(stats.total_pnl),
    },
    {
      label: 'Avg PnL',
      value: formatPnl(stats.avg_pnl),
      color: pnlColor(stats.avg_pnl),
    },
    {
      label: 'Avg Hold',
      value: stats.avg_holding_days > 0 ? `${stats.avg_holding_days}d` : '--',
    },
  ];

  return (
    <div className="flex flex-wrap gap-4">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <span className="text-xs text-[--text-muted] uppercase tracking-wider">
            {item.label}
          </span>
          <span
            className={`text-sm font-medium ${item.color || 'text-[--text-primary]'}`}
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}
