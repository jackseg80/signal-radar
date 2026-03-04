import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { VERDICT_COLORS, STRATEGY_LABELS } from '../../utils/format';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import RobustnessHeatmap from './RobustnessHeatmap';
import { X, Filter, ChevronUp, ChevronDown } from 'lucide-react';

const STRATEGY_MAPPING = {
  'rsi2': 'rsi2_mean_reversion',
  'ibs': 'ibs_mean_reversion',
  'tom': 'turn_of_month'
};

export default function ValidationsTable() {
  const { refreshKey } = useRefresh();
  const [filters, setFilters] = useState({
    strategy: '',
    universe: '',
    verdict: ''
  });
  const [sortConfig, setSortConfig] = useState({ key: 'profit_factor', direction: 'desc' });

  const { data, loading, error, refetch } = useApi(
    () => api.validations({ 
      strategy: STRATEGY_MAPPING[filters.strategy] || undefined, 
      universe: filters.universe || undefined, 
      verdict: filters.verdict || undefined 
    }),
    [refreshKey, filters]
  );

  const [selectedValidation, setSelectedValidation] = useState(null);

  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return <div className="w-4" />;
    return sortConfig.direction === 'asc' ? <ChevronUp size={14} className="text-green-400" /> : <ChevronDown size={14} className="text-green-400" />;
  };

  const sortedResults = useMemo(() => {
    const results = data?.results || [];
    if (!sortConfig.key) return results;

    return [...results].sort((a, b) => {
      let aVal = a[sortConfig.key];
      let bVal = b[sortConfig.key];

      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  const allStrategies = ['rsi2', 'ibs', 'tom'];
  const allUniverses = useMemo(() => {
    if (!data?.results?.length) return [];
    const univs = [...new Set(data.results.map(r => r.universe))].filter(Boolean).sort();
    return univs;
  }, [data]);

  if (loading && !sortedResults.length) return <LoadingState rows={10} />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const selectClass = "bg-[#1a1d27] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-green-500/50 cursor-pointer appearance-none min-w-[140px]";

  return (
    <div className="space-y-6">
      {/* Filters Bar */}
      <div className="flex flex-wrap gap-4 p-4 bg-white/[0.02] border border-white/5 rounded-xl">
        <div className="flex items-center gap-2 mr-2">
          <Filter size={14} className="text-[--text-muted]" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-[--text-muted]">Filtres :</span>
        </div>
        
        <div className="relative">
          <select
            value={filters.strategy}
            onChange={(e) => setFilters({ ...filters, strategy: e.target.value })}
            className={selectClass}
          >
            <option value="" className="bg-[#1a1d27]">Toutes les Stratégies</option>
            {allStrategies.map(s => <option key={s} value={s} className="bg-[#1a1d27]">{STRATEGY_LABELS[s] || s}</option>)}
          </select>
        </div>

        <div className="relative">
          <select
            value={filters.verdict}
            onChange={(e) => setFilters({ ...filters, verdict: e.target.value })}
            className={selectClass}
          >
            <option value="" className="bg-[#1a1d27]">Tous les Verdicts</option>
            <option value="VALIDATED" className="bg-[#1a1d27]">VALIDATED</option>
            <option value="CONDITIONAL" className="bg-[#1a1d27]">CONDITIONAL</option>
            <option value="REJECTED" className="bg-[#1a1d27]">REJECTED</option>
          </select>
        </div>

        <div className="relative">
          <select
            value={filters.universe}
            onChange={(e) => setFilters({ ...filters, universe: e.target.value })}
            className={selectClass}
          >
            <option value="" className="bg-[#1a1d27]">Tous les Univers</option>
            {allUniverses.map(u => <option key={u} value={u} className="bg-[#1a1d27]">{u}</option>)}
          </select>
        </div>
      </div>

      {sortedResults.length === 0 ? (
        <EmptyState message="Aucune validation ne correspond aux filtres" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-[--glass-border] text-[--text-muted] text-[10px] uppercase tracking-widest font-bold">
                <th className="text-left py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('strategy')}>
                  <div className="flex items-center gap-1">Stratégie {getSortIcon('strategy')}</div>
                </th>
                <th className="text-left py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('symbol')}>
                  <div className="flex items-center gap-1">Actif {getSortIcon('symbol')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('n_trades')}>
                  <div className="flex items-center justify-end gap-1">Trades {getSortIcon('n_trades')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('win_rate')}>
                  <div className="flex items-center justify-end gap-1">Win Rate {getSortIcon('win_rate')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('profit_factor')}>
                  <div className="flex items-center justify-end gap-1">PF {getSortIcon('profit_factor')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('sharpe')}>
                  <div className="flex items-center justify-end gap-1">Sharpe {getSortIcon('sharpe')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('robustness_pct')}>
                  <div className="flex items-center justify-end gap-1">Robust% {getSortIcon('robustness_pct')}</div>
                </th>
                <th className="text-center py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('verdict')}>
                  <div className="flex items-center justify-center gap-1">Verdict {getSortIcon('verdict')}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedResults.map((r, idx) => {
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
