import React, { useState, forwardRef } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, formatPnl, formatPct, formatDate, pnlColor, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import LiveTradeForm from './LiveTradeForm';

const LivePositions = forwardRef(({ style, className, onMouseDown, onMouseUp, onTouchEnd }, ref) => {
  const { refreshKey, refresh } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.liveOpenTrades(), [refreshKey]);
  const [closingTrade, setClosingTrade] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const handleDelete = async (trade) => {
    if (!window.confirm(`Delete ${trade.strategy}/${trade.symbol} trade?`)) return;
    setDeleting(trade.id);
    try {
      await api.liveDelete(trade.id);
      refresh();
    } catch (e) {
      alert(e.message);
    } finally {
      setDeleting(null);
    }
  };

  if (loading) return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Live Positions"
    >
      <LoadingState />
    </Card>
  );
  
  if (error) return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Live Positions"
    >
      <ErrorState message={error} onRetry={refetch} />
    </Card>
  );

  const trades = data?.trades || [];

  if (trades.length === 0) {
    return (
      <Card 
        ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
        title="Live Positions"
      >
        <EmptyState message="No open live trades" />
      </Card>
    );
  }

  return (
    <>
      <Card 
        ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
        title="Live Positions"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[--border-subtle] text-[--text-muted] text-xs uppercase tracking-wider">
                <th className="text-left py-2 px-2">Strategy</th>
                <th className="text-left py-2 px-2">Symbol</th>
                <th className="text-left py-2 px-2">Entry</th>
                <th className="text-right py-2 px-2">Entry $</th>
                <th className="text-right py-2 px-2">Current $</th>
                <th className="text-right py-2 px-2">Shares</th>
                <th className="text-right py-2 px-2">PnL</th>
                <th className="text-right py-2 px-2">%</th>
                <th className="text-right py-2 px-2"></th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => {
                const colors = STRATEGY_COLORS[t.strategy] || STRATEGY_COLORS.rsi2;
                return (
                  <tr key={t.id} className="border-b border-[--border-subtle]/50 hover:bg-[--bg-card-hover] transition-colors">
                    <td className="py-2.5 px-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text}`}>
                        {STRATEGY_LABELS[t.strategy] || t.strategy}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 font-medium">{t.symbol}</td>
                    <td className="py-2.5 px-2 text-[--text-secondary]">{formatDate(t.entry_date)}</td>
                    <td className="py-2.5 px-2 text-right text-[--text-secondary]">{formatPrice(t.entry_price)}</td>
                    <td className="py-2.5 px-2 text-right">{formatPrice(t.current_price)}</td>
                    <td className="py-2.5 px-2 text-right text-[--text-secondary]">{t.shares}</td>
                    <td className={`py-2.5 px-2 text-right font-medium ${pnlColor(t.unrealized_pnl)}`}>
                      {formatPnl(t.unrealized_pnl)}
                    </td>
                    <td className={`py-2.5 px-2 text-right ${pnlColor(t.unrealized_pct)}`}>
                      {formatPct(t.unrealized_pct)}
                    </td>
                    <td className="py-2.5 px-2 text-right space-x-1">
                      <button
                        onClick={() => setClosingTrade(t)}
                        className="px-2 py-0.5 rounded text-xs border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer"
                      >
                        Close
                      </button>
                      <button
                        onClick={() => handleDelete(t)}
                        disabled={deleting === t.id}
                        className="px-2 py-0.5 rounded text-xs border border-[--border-subtle] text-[--text-muted] hover:text-red-400 hover:border-red-500/30 transition-colors cursor-pointer disabled:opacity-50"
                        title="Delete trade"
                      >
                        {deleting === t.id ? '...' : 'Del'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {closingTrade && (
        <LiveTradeForm
          mode="close"
          prefill={{
            strategy: closingTrade.strategy,
            symbol: closingTrade.symbol,
          }}
          onDone={() => { setClosingTrade(null); refresh(); }}
          onCancel={() => setClosingTrade(null)}
        />
      )}
    </>
  );
});

LivePositions.displayName = "LivePositions";

export default LivePositions;
