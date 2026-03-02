import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, SIGNAL_COLORS, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';

const STRATEGY_ORDER = ['rsi2', 'ibs', 'tom'];

export default function MarketOverview() {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.marketOverview(), [refreshKey]);

  if (loading) return <Card title="Market Overview"><LoadingState rows={8} /></Card>;
  if (error) return <Card title="Market Overview"><ErrorState message={error} onRetry={refetch} /></Card>;

  const assets = data?.assets || [];
  if (assets.length === 0) {
    return <Card title="Market Overview"><EmptyState message="No market data" /></Card>;
  }

  // Determine which strategies are present
  const activeStrategies = STRATEGY_ORDER.filter((s) =>
    assets.some((a) => a.strategies[s])
  );

  return (
    <Card title="Market Overview">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[--border-subtle] text-[--text-muted] text-xs uppercase tracking-wider">
              <th className="text-left py-2 px-2">Symbol</th>
              <th className="text-right py-2 px-2">Close</th>
              {activeStrategies.map((s) => {
                const sc = STRATEGY_COLORS[s] || STRATEGY_COLORS.rsi2;
                return (
                  <th key={s} className="text-center py-2 px-2">
                    <span className={`${sc.text}`}>{STRATEGY_LABELS[s] || s}</span>
                  </th>
                );
              })}
              <th className="text-center py-2 px-2">Pos</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr
                key={a.symbol}
                className={`border-b border-[--border-subtle]/50 hover:bg-[--bg-card-hover] transition-colors ${
                  a.has_open_position ? 'bg-white/[0.02]' : ''
                }`}
              >
                <td className="py-2 px-2 font-medium">{a.symbol}</td>
                <td className="py-2 px-2 text-right text-[--text-secondary]">{formatPrice(a.close)}</td>
                {activeStrategies.map((s) => {
                  const strat = a.strategies[s];
                  if (!strat || strat.signal == null) {
                    return <td key={s} className="py-2 px-2 text-center text-[--text-muted]">--</td>;
                  }
                  const sig = SIGNAL_COLORS[strat.signal] || SIGNAL_COLORS.NO_SIGNAL;
                  return (
                    <td key={s} className="py-2 px-2 text-center">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${sig.bg} ${sig.text}`}>
                        {strat.signal === 'NO_SIGNAL' ? '--' : strat.signal}
                      </span>
                      {strat.indicator_value != null && (
                        <span className="ml-1 text-[10px] text-[--text-muted]">
                          {Number(strat.indicator_value).toFixed(s === 'ibs' ? 2 : s === 'rsi2' ? 1 : 0)}
                        </span>
                      )}
                    </td>
                  );
                })}
                <td className="py-2 px-2 text-center">
                  {a.has_open_position ? (
                    <span className="text-green-400 text-xs">
                      {a.position_strategies.map((s) => STRATEGY_LABELS[s] || s).join(', ')}
                    </span>
                  ) : (
                    <span className="text-[--text-muted]">--</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
