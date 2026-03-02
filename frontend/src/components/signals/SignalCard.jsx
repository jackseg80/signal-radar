import { formatPrice, SIGNAL_COLORS } from '../../utils/format';

const SIGNAL_GLOW = {
  BUY: 'glow-green',
  SELL: 'glow-red',
  SAFETY_EXIT: 'glow-red',
  WATCH: 'glow-amber',
  PENDING_VALID: 'glow-amber',
};

export default function SignalCard({ symbol, signal, close_price, indicator_value, notes }) {
  const colors = SIGNAL_COLORS[signal] || SIGNAL_COLORS.NO_SIGNAL;
  const isActionable = signal === 'BUY' || signal === 'SELL' || signal === 'SAFETY_EXIT';
  const isWatch = signal === 'WATCH' || signal === 'PENDING_VALID';
  const isDim = signal === 'NO_SIGNAL' || signal === 'PENDING_EXPIRED';
  const glowClass = SIGNAL_GLOW[signal] || 'shadow-card';

  return (
    <div className={`rounded-lg border border-[--border-subtle] border-l-4 ${colors.border} p-3 ${glowClass}
      ${isActionable || isWatch ? colors.bg : 'bg-[--bg-card]'}
      ${isDim ? 'opacity-40' : ''}
    `}>
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-sm ${isActionable ? 'font-bold text-[--text-primary]' : 'font-semibold text-[--text-secondary]'}`}>
          {symbol}
        </span>
        <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${colors.bg} ${colors.text}`}>
          {signal === 'NO_SIGNAL' ? '---' : signal.replace('_', ' ')}
        </span>
      </div>
      <div className="text-xs space-y-0.5">
        {close_price != null && (
          <div className="text-[--text-secondary]">{formatPrice(close_price)}</div>
        )}
        {notes && (
          <div className="text-[--text-muted] truncate" title={notes}>{notes}</div>
        )}
      </div>
    </div>
  );
}
