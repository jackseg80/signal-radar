import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { VERDICT_COLORS, STRATEGY_LABELS } from '../../utils/format';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import RobustnessHeatmap from './RobustnessHeatmap';
import { X, Filter } from 'lucide-react';

export default function ValidationsTable() {
  const { refreshKey } = useRefresh();
  const [filters, setFilters] = useState({
    strategy: '',
    universe: '',
    verdict: ''
  });

  const { data, loading, error, refetch } = useApi(
    () => api.validations({ 
      strategy: filters.strategy || undefined, 
      universe: filters.universe || undefined, 
      verdict: filters.verdict || undefined 
    }),
    [refreshKey, filters]
  );

  const [selectedValidation, setSelectedValidation] = useState(null);

  const results = data?.results || [];

  // Get unique values for filters from ALL results (we might need a separate API call for this in the future
  // but for now we'll use the current results or common known values)
  const allStrategies = useMemo(() => {
    return ['rsi2', 'ibs', 'tom'];
  }, []);

  const allUniverses = useMemo(() => {
    if (!results.length) return [];
    return [...new Set(results.map(r => r.universe))].sort();
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
          value={filters.verdict}
          onChange={(e) => setFilters({ ...filters, verdict: e.target.value })}
          className="bg-[--bg-primary] border border-[--glass-border] rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-green-500/50 cursor-pointer"
        >
          <option value="">Tous les Verdicts</option>
          <option value="VALIDATED">VALIDATED</option>
          <option value="CONDITIONAL">CONDITIONAL</option>
          <option value="REJECTED">REJECTED</option>
        </select>

        {allUniverses.length > 0 && (
          <select
            value={filters.universe}
            onChange={(e) => setFilters({ ...filters, universe: e.target.value })}
            className="bg-[--bg-primary] border border-[--glass-border] rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-green-500/50 cursor-pointer"
          >
            <option value="">Tous les Univers</option>
            {allUniverses.map(u => <option key={u} value={u}>{u}</option>)}
          </select>
        )}
      </div>

      {results.length === 0 ? (
        <EmptyState message="Aucune validation ne correspond aux filtres" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-[--glass-border] text-[--text-muted] text-[10px] uppercase tracking-widest font-bold">
                <th className="text-left py-4 px-4">Stratégie</th>
                <th className="text-left py-4 px-4">Actif</th>
                <th className="text-right py-4 px-4">Trades</th>
                <th className="text-right py-4 px-4">Win Rate</th>
                <th className="text-right py-4 px-4">PF</th>
                <th className="text-right py-4 px-4">Sharpe</th>
                <th className="text-right py-4 px-4">Robust%</th>
                <th className="text-center py-4 px-4">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, idx) => {
                const v = VERDICT_COLORS[r.verdict] || VERDICT_COLORS.REJECTED;
                const isSelected = selectedValidation?.symbol === r.symbol && selectedValidation?.strategy === r.strategy;
                const baseStrategy = r.strategy.split('_')[0];
                
                return (
                  <tr
                    key={`${r.strategy}-${r.symbol}-${idx}`}
                    className={`border-b border-white/5 hover:bg-white/[0.04] transition-colors cursor-pointer group ${
                      isSelected ? 'bg-green-500/[0.05] border-green-500/20' : ''
                    }`}
                    onClick={() => setSelectedValidation(r)}
                  >
                    <td className="py-4 px-4">
                      <span className="text-white font-medium">{STRATEGY_LABELS[baseStrategy] || baseStrategy}</span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="text-white font-bold group-hover:text-green-400 transition-colors">{r.symbol}</span>
                    </td>
                    <td className="py-4 px-4 text-right tabular-nums text-[--text-secondary]">
                      {r.n_trades}
                    </td>
                    <td className="py-4 px-4 text-right tabular-nums text-[--text-secondary]">
                      {(r.win_rate * 100).toFixed(0)}%
                    </td>
                    <td className={`py-4 px-4 text-right tabular-nums font-bold ${r.profit_factor >= 1.5 ? 'text-green-400' : r.profit_factor >= 1 ? 'text-white' : 'text-red-400'}`}>
                      {r.profit_factor.toFixed(2)}
                    </td>
                    <td className="py-4 px-4 text-right tabular-nums text-[--text-secondary]">
                      {r.sharpe ? r.sharpe.toFixed(2) : '--'}
                    </td>
                    <td className="py-4 px-4 text-right tabular-nums">
                      <div className="flex flex-col items-end">
                        <span className={r.robustness_pct >= 80 ? 'text-green-400' : 'text-amber-400'}>
                          {r.robustness_pct.toFixed(0)}%
                        </span>
                        <div className="w-12 h-0.5 bg-white/5 rounded-full mt-1">
                          <div 
                            className={`h-full rounded-full ${r.robustness_pct >= 80 ? 'bg-green-500' : 'bg-amber-500'}`}
                            style={{ width: `${r.robustness_pct}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-4 text-center">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest border ${v.bg} ${v.text} ${v.border}`}>
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

      {/* Robustness Matrix View */}
      {selectedValidation && (
        <div className="animate-fade-in relative">
          <button 
            onClick={() => setSelectedValidation(null)}
            className="absolute right-4 top-4 z-10 p-2 rounded-full hover:bg-white/5 text-[--text-muted] hover:text-white transition-colors cursor-pointer"
          >
            <X size={20} />
          </button>
          <RobustnessHeatmap 
            strategy={selectedValidation.strategy.split('_')[0]} 
            symbol={selectedValidation.symbol} 
            universe={selectedValidation.universe}
          />
        </div>
      )}
    </div>
  );
}
