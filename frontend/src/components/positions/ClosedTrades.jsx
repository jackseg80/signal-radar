import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, formatPnl, formatPct, formatDate, pnlColor, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import PnlBar from '../ui/PnlBar';

export default function ClosedTrades({ className }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(
    () => api.closedTrades({ limit: 10 }),
    [refreshKey],
  );

  if (loading) return <Card title="Recent Trades" className={className}><LoadingState /></Card>;
  if (error) return <Card title="Recent Trades" className={className}><ErrorState message={error} onRetry={refetch} /></Card>;

  const trades = data?.trades || [];

  if (trades.length === 0) {
    return <Card title="Recent Trades" className={className}><EmptyState message="No closed trades yet" /></Card>;
  }

  const maxAbsPnl = Math.max(1, ...trades.map((t) => Math.abs(t.pnl_dollars || 0)));

  return (
    <Card title="Recent Trades" className={className}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[--border-subtle] text-[--text-muted] text-xs uppercase tracking-wider">
              <th className="text-left py-2 px-2">Strategy</th>
              <th className="text-left py-2 px-2">Symbol</th>
              <th className="text-left py-2 px-2">Entry</th>
              <th className="text-left py-2 px-2">Exit</th>
              <th className="text-right py-2 px-2">Entry $</th>
              <th className="text-right py-2 px-2">Exit $</th>
              <th className="text-right py-2 px-2">PnL</th>
              <th className="text-right py-2 px-2">%</th>
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
                  <td className="py-2.5 px-2 text-[--text-secondary]">{formatDate(t.exit_date)}</td>
                  <td className="py-2.5 px-2 text-right text-[--text-secondary]">{formatPrice(t.entry_price)}</td>
                  <td className="py-2.5 px-2 text-right text-[--text-secondary]">{formatPrice(t.exit_price)}</td>
                  <td className={`py-2.5 px-2 text-right font-medium ${pnlColor(t.pnl_dollars)}`}>
                    <div>{formatPnl(t.pnl_dollars)}</div>
                    <PnlBar value={t.pnl_dollars} maxAbs={maxAbsPnl} width={50} />
                  </td>
                  <td className={`py-2.5 px-2 text-right ${pnlColor(t.pnl_pct)}`}>
                    {formatPct(t.pnl_pct)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {data.total > 10 && (
        <div className="text-center mt-3 text-xs text-[--text-muted]">
          Showing 10 of {data.total} trades
        </div>
      )}
    </Card>
  );
}
