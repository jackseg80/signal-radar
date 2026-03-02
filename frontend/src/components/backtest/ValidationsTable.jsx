import { useState } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPF, STRATEGY_COLORS, STRATEGY_LABELS, VERDICT_COLORS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';

export default function ValidationsTable() {
  const { refreshKey } = useRefresh();
  const [strategy, setStrategy] = useState('');
  const [universe, setUniverse] = useState('');
  const [verdict, setVerdict] = useState('');

  const { data, loading, error, refetch } = useApi(
    () => api.validations({ strategy: strategy || undefined, universe: universe || undefined, verdict: verdict || undefined }),
    [refreshKey, strategy, universe, verdict],
  );

  const results = data?.results || [];

  // Extract unique values for filter dropdowns
  const allStrategies = [...new Set(results.map((r) => r.strategy))].sort();
  const allUniverses = [...new Set(results.map((r) => r.universe))].sort();

  return (
    <Card title="Validations">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
          className="bg-[--bg-primary] border border-[--border-subtle] rounded px-3 py-1.5 text-xs text-[--text-secondary] cursor-pointer"
        >
          <option value="">All strategies</option>
          {allStrategies.map((s) => (
            <option key={s} value={s}>{STRATEGY_LABELS[s] || s}</option>
          ))}
        </select>
        <select
          value={universe}
          onChange={(e) => setUniverse(e.target.value)}
          className="bg-[--bg-primary] border border-[--border-subtle] rounded px-3 py-1.5 text-xs text-[--text-secondary] cursor-pointer"
        >
          <option value="">All universes</option>
          {allUniverses.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <select
          value={verdict}
          onChange={(e) => setVerdict(e.target.value)}
          className="bg-[--bg-primary] border border-[--border-subtle] rounded px-3 py-1.5 text-xs text-[--text-secondary] cursor-pointer"
        >
          <option value="">All verdicts</option>
          <option value="VALIDATED">VALIDATED</option>
          <option value="CONDITIONAL">CONDITIONAL</option>
          <option value="REJECTED">REJECTED</option>
        </select>
      </div>

      {loading && <LoadingState rows={5} />}
      {error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && results.length === 0 && (
        <EmptyState message="No validation results found" />
      )}
      {!loading && !error && results.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[--border-subtle] text-[--text-muted] text-xs uppercase tracking-wider">
                <th className="text-left py-2 px-2">Symbol</th>
                <th className="text-left py-2 px-2">Strategy</th>
                <th className="text-left py-2 px-2">Universe</th>
                <th className="text-right py-2 px-2">Trades</th>
                <th className="text-right py-2 px-2">WR</th>
                <th className="text-right py-2 px-2">PF</th>
                <th className="text-right py-2 px-2">Sharpe</th>
                <th className="text-right py-2 px-2">Robust%</th>
                <th className="text-right py-2 px-2">p-val</th>
                <th className="text-center py-2 px-2">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => {
                const sc = STRATEGY_COLORS[r.strategy] || STRATEGY_COLORS.rsi2;
                const vc = VERDICT_COLORS[r.verdict] || {};
                return (
                  <tr key={i} className="border-b border-[--border-subtle]/50 hover:bg-[--bg-card-hover] transition-colors">
                    <td className="py-2.5 px-2 font-medium">{r.symbol}</td>
                    <td className="py-2.5 px-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${sc.bg} ${sc.text}`}>
                        {STRATEGY_LABELS[r.strategy] || r.strategy}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-[--text-secondary] text-xs">{r.universe}</td>
                    <td className="py-2.5 px-2 text-right">{r.n_trades}</td>
                    <td className="py-2.5 px-2 text-right">{r.win_rate != null ? `${(r.win_rate * 100).toFixed(1)}%` : '--'}</td>
                    <td className="py-2.5 px-2 text-right font-medium">{formatPF(r.profit_factor)}</td>
                    <td className="py-2.5 px-2 text-right text-[--text-secondary]">{r.sharpe != null ? r.sharpe.toFixed(2) : '--'}</td>
                    <td className="py-2.5 px-2 text-right">{r.robustness_pct != null ? `${r.robustness_pct.toFixed(0)}%` : '--'}</td>
                    <td className="py-2.5 px-2 text-right text-[--text-secondary]">{r.p_value != null ? r.p_value.toFixed(4) : '--'}</td>
                    <td className="py-2.5 px-2 text-center">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${vc.bg || ''} ${vc.text || ''}`}>
                        {r.verdict}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
