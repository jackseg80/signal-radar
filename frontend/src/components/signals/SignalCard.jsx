import { formatPrice, SIGNAL_COLORS } from '../../utils/format';

const SIGNAL_GLOW = {
  BUY: 'glow-green',
  SELL: 'glow-red',
  SAFETY_EXIT: 'glow-red',
  WATCH: 'glow-amber',
  PENDING_VALID: 'glow-amber',
};

const SIGNAL_ICONS = {
  BUY: '\u25B2',
  SELL: '\u25BC',
  SAFETY_EXIT: '\u26A0',
  HOLD: '\u2022',
  WATCH: '\u25CB',
};

export default function SignalCard({ symbol, signal, close_price, indicator_value, notes }) {
  const colors = SIGNAL_COLORS[signal] || SIGNAL_COLORS.NO_SIGNAL;
  const isActionable = signal === 'BUY' || signal === 'SELL' || signal === 'SAFETY_EXIT';
  const isWatch = signal === 'WATCH' || signal === 'PENDING_VALID';
  const isDim = signal === 'NO_SIGNAL' || signal === 'PENDING_EXPIRED';
  const glowClass = SIGNAL_GLOW[signal] || '';
  const icon = SIGNAL_ICONS[signal] || '';

  return (
    <div className={`rounded-lg border border-l-4 ${colors.border} p-3 transition-all duration-200
      ${isActionable || isWatch ? `glass-card ${glowClass}` : 'bg-[--bg-card] shadow-card'}
      ${isActionable && signal === 'BUY' ? 'animate-border-glow' : ''}
      ${isDim ? 'opacity-40' : ''}
      hover:scale-[1.02] hover:brightness-110
    `}>
      <div className="flex items-center justify-between mb-1.5">
        <span className={`text-sm ${isActionable ? 'font-bold text-[--text-primary]' : 'font-semibold text-[--text-secondary]'}`}>
          {symbol}
        </span>
        <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${colors.bg} ${colors.text} flex items-center gap-1`}>
          {icon && <span className="text-[9px]">{icon}</span>}
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
