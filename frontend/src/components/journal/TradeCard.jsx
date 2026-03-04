import {
  formatPrice,
  formatPnl,
  formatPct,
  formatDate,
  pnlColor,
  STRATEGY_COLORS,
  STRATEGY_LABELS,
} from '../../utils/format';
import NoteEditor from './NoteEditor';

const SOURCE_BADGE = {
  paper: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'PAPER' },
  live: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'LIVE' },
};

function formatSignalDetails(details, strategy) {
  if (!details) return null;
  const parts = [];

  if (strategy === 'rsi2') {
    if (details.rsi != null) parts.push(`RSI=${Number(details.rsi).toFixed(1)}`);
    if (details.sma200 != null) parts.push(`SMA200=${formatPrice(details.sma200)}`);
    if (details.trend_ok != null) parts.push(details.trend_ok ? 'trend ok' : 'no trend');
  } else if (strategy === 'ibs') {
    if (details.ibs != null) parts.push(`IBS=${Number(details.ibs).toFixed(2)}`);
    if (details.sma200 != null) parts.push(`SMA200=${formatPrice(details.sma200)}`);
    if (details.trend_ok != null) parts.push(details.trend_ok ? 'trend ok' : 'no trend');
  } else if (strategy === 'tom') {
    if (details.trading_days_left != null) {
      parts.push(`${details.trading_days_left}d left in month`);
    }
    if (details.entry_days_before_eom != null) {
      parts.push(`window=${details.entry_days_before_eom}`);
    }
  }

  return parts.length > 0 ? parts.join(', ') : null;
}

export default function TradeCard({ entry, onSaved }) {
  const stratColors = STRATEGY_COLORS[entry.strategy] || STRATEGY_COLORS.rsi2;
  const stratLabel = STRATEGY_LABELS[entry.strategy] || entry.strategy;
  const srcBadge = SOURCE_BADGE[entry.source] || SOURCE_BADGE.paper;
  const isOpen = entry.status === 'open';
  const signalText = formatSignalDetails(entry.signal_details, entry.strategy);

  return (
    <div
      className={`glass-card rounded-lg p-4 border-l-2 ${stratColors.border} animate-fade-in`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${srcBadge.bg} ${srcBadge.text}`}
          >
            {srcBadge.label}
          </span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${stratColors.bg} ${stratColors.text}`}>
            {stratLabel}
          </span>
          {isOpen && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/20 text-amber-400">
              OPEN
            </span>
          )}
          <span className="text-sm font-semibold text-[--text-primary]">{entry.symbol}</span>
        </div>

        {entry.pnl_dollars != null && (
          <span
            className={`text-sm font-bold ${pnlColor(entry.pnl_dollars)}`}
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {formatPnl(entry.pnl_dollars)}
          </span>
        )}
      </div>

      {/* Price line */}
      <div className="text-xs text-[--text-secondary] mb-1">
        <span>{formatPrice(entry.entry_price)}</span>
        {entry.exit_price != null && (
          <>
            <span className="text-[--text-muted] mx-1">&rarr;</span>
            <span>{formatPrice(entry.exit_price)}</span>
          </>
        )}
        <span className="text-[--text-muted] mx-1">|</span>
        <span>{formatDate(entry.entry_date)}</span>
        {entry.exit_date && (
          <>
            <span className="text-[--text-muted] mx-1">&rarr;</span>
            <span>{formatDate(entry.exit_date)}</span>
          </>
        )}
        {entry.holding_days != null && (
          <span className="text-[--text-muted] ml-1">({entry.holding_days}d)</span>
        )}
        {entry.pnl_pct != null && (
          <>
            <span className="text-[--text-muted] mx-1">|</span>
            <span className={pnlColor(entry.pnl_pct)}>{formatPct(entry.pnl_pct)}</span>
          </>
        )}
      </div>

      {/* Details */}
      <div className="text-xs text-[--text-muted] mb-2">
        <span>Shares: {entry.shares}</span>
        {entry.fees > 0 && <span className="ml-3">Fees: {formatPrice(entry.fees)}</span>}
        {signalText && (
          <>
            <span className="mx-1">|</span>
            <span className="text-[--text-secondary]">{signalText}</span>
          </>
        )}
      </div>

      {/* Slippage (live only) */}
      {entry.slippage && (
        <div className="text-xs text-[--text-muted] mb-2 px-2 py-1 rounded bg-white/5">
          <span>vs paper: </span>
          <span>
            entry {entry.slippage.entry_diff >= 0 ? '+' : ''}
            {formatPrice(entry.slippage.entry_diff)}
          </span>
          {entry.slippage.exit_diff != null && (
            <span>
              , exit {entry.slippage.exit_diff >= 0 ? '+' : ''}
              {formatPrice(entry.slippage.exit_diff)}
            </span>
          )}
          {entry.slippage.pnl_diff != null && (
            <span className={pnlColor(entry.slippage.pnl_diff)}>
              , PnL {formatPnl(entry.slippage.pnl_diff)}
            </span>
          )}
        </div>
      )}

      {/* Notes & Tags & Sentiment */}
      <NoteEditor
        notes={entry.notes}
        tags={entry.tags}
        sentiment={entry.sentiment}
        source={entry.source}
        id={entry.id}
        onSaved={onSaved}
      />
    </div>
  );
}
