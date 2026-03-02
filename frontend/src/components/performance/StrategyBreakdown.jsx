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
    {
      label: 'Capital',
      value: `$${capital.toLocaleString()}`,
      color: 'text-[--text-primary]',
      glow: '',
    },
    {
      label: 'Realized',
      value: formatPnl(total_realized_pnl),
      sub: formatPct(realizedPct),
      color: pnlColor(total_realized_pnl),
      glow: total_realized_pnl > 0 ? 'glow-green' : total_realized_pnl < 0 ? 'glow-red' : 'shadow-card',
    },
    {
      label: 'Unrealized',
      value: formatPnl(total_unrealized_pnl),
      sub: formatPct(unrealizedPct),
      color: pnlColor(total_unrealized_pnl),
      glow: total_unrealized_pnl > 0 ? 'glow-green' : total_unrealized_pnl < 0 ? 'glow-red' : 'shadow-card',
    },
    {
      label: 'Win Rate',
      value: win_rate != null ? `${win_rate.toFixed(1)}%` : '--',
      color: 'text-[--text-primary]',
      glow: 'shadow-card',
    },
    {
      label: 'Trades',
      value: `${n_closed_trades} / ${n_open_positions}`,
      sub: 'closed / open',
      color: 'text-[--text-primary]',
      glow: 'shadow-card',
    },
  ];

  return (
    <div className="space-y-4">
      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {kpis.map((kpi) => (
          <div
            key={kpi.label}
            className={`bg-[--bg-card] rounded-lg p-4 border border-[--border-subtle] ${kpi.glow || 'shadow-card'}`}
          >
            <div
              className="text-[10px] font-semibold uppercase tracking-widest text-[--text-muted] mb-2"
              style={{ fontFamily: "'Space Grotesk', sans-serif" }}
            >
              {kpi.label}
            </div>
            <div className={`text-2xl font-bold tabular-nums ${kpi.color}`}>{kpi.value}</div>
            {kpi.sub && (
              <div className="text-xs text-[--text-muted] mt-1">{kpi.sub}</div>
            )}
          </div>
        ))}
      </div>

      {/* Strategy breakdown */}
      {by_strategy && Object.keys(by_strategy).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {Object.entries(by_strategy).map(([strat, stats]) => {
            const colors = STRATEGY_COLORS[strat] || STRATEGY_COLORS.rsi2;
            return (
              <div
                key={strat}
                className={`bg-[--bg-card] rounded-lg p-4 border border-[--border-subtle] border-t-2 ${colors.border} shadow-card`}
              >
                <div className="flex items-center gap-2 mb-3">
                  <span
                    className={`px-2.5 py-1 rounded-md text-xs font-bold ${colors.bg} ${colors.text}`}
                    style={{ fontFamily: "'Space Grotesk', sans-serif" }}
                  >
                    {STRATEGY_LABELS[strat] || strat}
                  </span>
                </div>
                <div className="text-sm space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-[--text-muted] text-xs">Trades</span>
                    <span className="font-medium">
                      {stats.trades}
                      <span className="text-[--text-muted] font-normal ml-1">
                        ({stats.wins}W / {stats.trades - stats.wins}L)
                      </span>
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[--text-muted] text-xs">PnL</span>
                    <span className={`font-bold ${pnlColor(stats.pnl)}`}>{formatPnl(stats.pnl)}</span>
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
