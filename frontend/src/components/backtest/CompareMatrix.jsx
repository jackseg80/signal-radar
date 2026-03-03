import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPF, STRATEGY_COLORS, STRATEGY_LABELS, VERDICT_COLORS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import HeatCell from '../ui/HeatCell';

export default function CompareMatrix() {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.compare(), [refreshKey]);

  if (loading) return <Card title="Strategy Comparison"><LoadingState rows={6} /></Card>;
  if (error) return <Card title="Strategy Comparison"><ErrorState message={error} onRetry={refetch} /></Card>;

  const { assets = [], strategies = [], matrix = {} } = data || {};

  if (assets.length === 0 || strategies.length === 0) {
    return (
      <Card title="Strategy Comparison">
        <EmptyState message="No validation data. Run: python -m cli.validate rsi2 us_stocks_large" />
      </Card>
    );
  }

  return (
    <Card title="Strategy Comparison">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[--border-subtle]">
              <th className="text-left py-2 px-3 text-[--text-muted] text-xs uppercase tracking-wider">Asset</th>
              {strategies.map((s) => {
                const colors = STRATEGY_COLORS[s] || STRATEGY_COLORS.rsi2;
                return (
                  <th key={s} className="text-center py-2 px-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text}`}>
                      {STRATEGY_LABELS[s] || s}
                    </span>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {assets.map((sym) => (
              <tr key={sym} className="border-b border-[--border-subtle]/50 hover:bg-[--bg-card-hover] transition-colors">
                <td className="py-2.5 px-3 font-medium">{sym}</td>
                {strategies.map((s) => {
                  const cell = matrix[sym]?.[s];
                  if (!cell) {
                    return (
                      <td key={s} className="py-2.5 px-3 text-center text-[--text-muted]">--</td>
                    );
                  }
                  const vc = VERDICT_COLORS[cell.verdict] || {};
                  return (
                    <HeatCell
                      key={s}
                      value={cell.pf}
                      min={0.8}
                      max={2.5}
                      scale="sequential"
                    >
                      <span className="font-mono font-medium">{formatPF(cell.pf)}</span>
                      <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold ${vc.bg || ''} ${vc.text || ''}`}>
                        {cell.verdict === 'VALIDATED' ? 'V' : cell.verdict === 'CONDITIONAL' ? '~' : 'X'}
                      </span>
                    </HeatCell>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
