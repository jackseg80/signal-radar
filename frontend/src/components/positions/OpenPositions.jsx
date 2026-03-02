import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, formatPnl, formatPct, formatDate, pnlColor, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';

export default function OpenPositions({ onLogReal }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.openPositions(), [refreshKey]);

  if (loading) return <Card title="Open Positions"><LoadingState /></Card>;
  if (error) return <Card title="Open Positions"><ErrorState message={error} onRetry={refetch} /></Card>;

  const positions = data?.positions || [];

  if (positions.length === 0) {
    return <Card title="Open Positions"><EmptyState message="No open positions" /></Card>;
  }

  return (
    <Card title="Open Positions">
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
              {onLogReal && <th className="text-right py-2 px-2"></th>}
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const colors = STRATEGY_COLORS[p.strategy] || STRATEGY_COLORS.rsi2;
              return (
                <tr key={p.id} className="border-b border-[--border-subtle]/50 hover:bg-[--bg-card-hover] transition-colors">
                  <td className="py-2.5 px-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text}`}>
                      {STRATEGY_LABELS[p.strategy] || p.strategy}
                    </span>
                  </td>
                  <td className="py-2.5 px-2 font-medium">{p.symbol}</td>
                  <td className="py-2.5 px-2 text-[--text-secondary]">{formatDate(p.entry_date)}</td>
                  <td className="py-2.5 px-2 text-right text-[--text-secondary]">{formatPrice(p.entry_price)}</td>
                  <td className="py-2.5 px-2 text-right">{formatPrice(p.current_price)}</td>
                  <td className="py-2.5 px-2 text-right text-[--text-secondary]">{p.shares}</td>
                  <td className={`py-2.5 px-2 text-right font-medium ${pnlColor(p.unrealized_pnl)}`}>
                    {formatPnl(p.unrealized_pnl)}
                  </td>
                  <td className={`py-2.5 px-2 text-right ${pnlColor(p.unrealized_pct)}`}>
                    {formatPct(p.unrealized_pct)}
                  </td>
                  {onLogReal && (
                    <td className="py-2.5 px-2 text-right">
                      <button
                        onClick={() => onLogReal({
                          strategy: p.strategy,
                          symbol: p.symbol,
                          date: p.entry_date,
                          price: p.entry_price,
                          shares: p.shares,
                          paper_position_id: p.id,
                        })}
                        className="px-2 py-0.5 rounded text-xs border border-green-500/30 text-green-400 hover:bg-green-500/10 transition-colors cursor-pointer whitespace-nowrap"
                      >
                        Log Real
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-[--border-subtle]">
              <td colSpan={onLogReal ? 7 : 6} className="py-2.5 px-2 text-right text-xs text-[--text-muted] uppercase">Total unrealized</td>
              <td colSpan={onLogReal ? 2 : 2} className={`py-2.5 px-2 text-right font-semibold ${pnlColor(data.total_unrealized_pnl)}`}>
                {formatPnl(data.total_unrealized_pnl)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Card>
  );
}
