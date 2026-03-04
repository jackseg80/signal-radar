import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPF, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import { Filter } from 'lucide-react';

export default function ScreensTable() {
  const { refreshKey } = useRefresh();
  const [filters, setFilters] = useState({
    strategy: '',
    universe: '',
    minPf: '1.0'
  });

  const { data, loading, error, refetch } = useApi(
    () => api.screens({
      strategy: filters.strategy || undefined,
      universe: filters.universe || undefined,
      min_pf: parseFloat(filters.minPf) || 0,
    }),
    [refreshKey, filters],
  );

  const results = data?.results || [];

  // Get unique values for filters
  // Note: we'd need a separate endpoint to get ALL strategies/universes if results are empty
  const allStrategies = useMemo(() => ['rsi2', 'ibs', 'tom'], []);
  
  const allUniverses = useMemo(() => {
    if (!results.length) return [];
    return [...new Set(results.map((r) => r.universe))].sort();
  }, [results]);

  if (loading && !results.length) return <LoadingState rows={10} />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-6">
      {/* Filters Bar */}
      <div className="flex flex-wrap gap-4 p-4 bg-white/[0.02] border border-white/5 rounded-xl">
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-[--text-muted]" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-[--text-muted]">Filtres :</span>
        </div>
        
        <select
          value={filters.strategy}
          onChange={(e) => setFilters({ ...filters, strategy: e.target.value })}
          className="bg-[--bg-primary] border border-[--glass-border] rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-green-500/50 cursor-pointer"
        >
          <option value="">Toutes les Stratégies</option>
          {allStrategies.map(s => <option key={s} value={s}>{STRATEGY_LABELS[s] || s}</option>)}
        </select>

        <select
          value={filters.universe}
          onChange={(e) => setFilters({ ...filters, universe: e.target.value })}
          className="bg-[--bg-primary] border border-[--glass-border] rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-green-500/50 cursor-pointer"
        >
          <option value="">Tous les Univers</option>
          {allUniverses.map(u => <option key={u} value={u}>{u}</option>)}
        </select>

        <div className="flex items-center gap-2 bg-[--bg-primary] border border-[--glass-border] rounded-lg px-3 py-1.5">
          <label className="text-[10px] font-bold text-[--text-muted] uppercase">Min PF:</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value={filters.minPf}
            onChange={(e) => setFilters({ ...filters, minPf: e.target.value })}
            className="bg-transparent border-none text-xs text-white w-12 outline-none"
          />
        </div>
      </div>

      {results.length === 0 ? (
        <EmptyState message="Aucun résultat de screening ne correspond aux filtres" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-[--glass-border] text-[--text-muted] text-[10px] uppercase tracking-widest font-bold">
                <th className="text-left py-4 px-4">Actif</th>
                <th className="text-left py-4 px-4">Stratégie</th>
                <th className="text-left py-4 px-4">Univers</th>
                <th className="text-right py-4 px-4">Trades</th>
                <th className="text-right py-4 px-4">WR</th>
                <th className="text-right py-4 px-4">PF</th>
                <th className="text-right py-4 px-4">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => {
                const sc = STRATEGY_COLORS[r.strategy] || STRATEGY_COLORS.rsi2;
                return (
                  <tr key={i} className="border-b border-white/5 hover:bg-white/[0.04] transition-colors group">
                    <td className="py-4 px-4">
                      <span className="font-bold text-white group-hover:text-green-400 transition-colors">{r.symbol}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest ${sc.bg} ${sc.text}`}>
                        {STRATEGY_LABELS[r.strategy] || r.strategy}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-[--text-muted] text-xs">{r.universe}</td>
                    <td className="py-4 px-4 text-right tabular-nums">{r.n_trades}</td>
                    <td className="py-4 px-4 text-right tabular-nums">{r.win_rate != null ? `${(r.win_rate * 100).toFixed(1)}%` : '--'}</td>
                    <td className={`py-4 px-4 text-right tabular-nums font-bold ${r.profit_factor >= 1.5 ? 'text-green-400' : 'text-white'}`}>
                      {formatPF(r.profit_factor)}
                    </td>
                    <td className="py-4 px-4 text-right tabular-nums text-[--text-muted]">{r.sharpe != null ? r.sharpe.toFixed(2) : '--'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {data?.total > 0 && (
        <div className="text-right mt-3 text-[10px] font-bold uppercase tracking-widest text-[--text-muted]">
          {data.total} résultats trouvés
        </div>
      )}
    </div>
  );
}
