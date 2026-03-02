import { formatPrice, SIGNAL_COLORS } from '../../utils/format';

export default function SignalCard({ symbol, signal, close_price, indicator_value, notes }) {
  const colors = SIGNAL_COLORS[signal] || SIGNAL_COLORS.NO_SIGNAL;
  const isActionable = signal === 'BUY' || signal === 'SELL' || signal === 'SAFETY_EXIT';
  const isWatch = signal === 'WATCH' || signal === 'PENDING_VALID';

  return (
    <div className={`rounded-lg border border-[--border-subtle] border-l-4 ${colors.border} ${isActionable ? colors.bg : isWatch ? colors.bg : 'bg-[--bg-card]'} p-3`}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-semibold text-sm">{symbol}</span>
        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${colors.bg} ${colors.text}`}>
          {signal === 'NO_SIGNAL' ? '---' : signal}
        </span>
      </div>
      <div className="text-xs text-[--text-secondary] space-y-0.5">
        {close_price != null && (
          <div>{formatPrice(close_price)}</div>
        )}
        {notes && (
          <div className="text-[--text-muted]">{notes}</div>
        )}
      </div>
    </div>
  );
}
