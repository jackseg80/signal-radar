import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPnl, formatPct, pnlColor, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';

export default function StrategyBreakdown() {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.perfSummary(), [refreshKey]);

  if (loading) return <Card><LoadingState rows={2} /></Card>;
  if (error) return <Card><ErrorState message={error} onRetry={refetch} /></Card>;
  if (!data) return null;

  const {
    capital, n_closed_trades, n_wins, win_rate,
    total_realized_pnl, total_unrealized_pnl, n_open_positions, by_strategy,
  } = data;

  const realizedPct = capital > 0 ? (total_realized_pnl / capital * 100) : 0;
  const unrealizedPct = capital > 0 ? (total_unrealized_pnl / capital * 100) : 0;

  const kpis = [
    { label: 'Capital', value: `$${capital.toLocaleString()}`, color: 'text-[--text-primary]' },
    { label: 'Realized', value: formatPnl(total_realized_pnl), sub: formatPct(realizedPct), color: pnlColor(total_realized_pnl) },
    { label: 'Unrealized', value: formatPnl(total_unrealized_pnl), sub: formatPct(unrealizedPct), color: pnlColor(total_unrealized_pnl) },
    { label: 'Win Rate', value: win_rate != null ? `${win_rate.toFixed(1)}%` : '--', color: 'text-[--text-primary]' },
    { label: 'Trades', value: `${n_closed_trades} / ${n_open_positions}`, sub: 'closed / open', color: 'text-[--text-primary]' },
  ];

  return (
    <div className="space-y-4">
      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="bg-[--bg-card] rounded-lg p-4 border border-[--border-subtle]">
            <div className="text-xs text-[--text-muted] uppercase tracking-wider mb-1" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              {kpi.label}
            </div>
            <div className={`text-lg font-semibold ${kpi.color}`}>{kpi.value}</div>
            {kpi.sub && <div className="text-xs text-[--text-muted] mt-0.5">{kpi.sub}</div>}
          </div>
        ))}
      </div>

      {/* Strategy breakdown */}
      {by_strategy && Object.keys(by_strategy).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {Object.entries(by_strategy).map(([strat, stats]) => {
            const colors = STRATEGY_COLORS[strat] || STRATEGY_COLORS.rsi2;
            return (
              <div key={strat} className={`bg-[--bg-card] rounded-lg p-4 border border-[--border-subtle] border-t-2 ${colors.border}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text}`}>
                    {STRATEGY_LABELS[strat] || strat}
                  </span>
                </div>
                <div className="text-sm space-y-1">
                  <div className="flex justify-between">
                    <span className="text-[--text-muted]">Trades</span>
                    <span>{stats.trades} ({stats.wins}W / {stats.trades - stats.wins}L)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[--text-muted]">PnL</span>
                    <span className={pnlColor(stats.pnl)}>{formatPnl(stats.pnl)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
