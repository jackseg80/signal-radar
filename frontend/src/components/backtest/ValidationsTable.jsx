import React, { useState } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { VERDICT_COLORS } from '../../utils/format';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import RobustnessHeatmap from './RobustnessHeatmap';
import { X } from 'lucide-react';

export default function ValidationsTable({ strategy, universe, verdict }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(
    () => api.validations({ strategy: strategy || undefined, universe: universe || undefined, verdict: verdict || undefined }),
    [refreshKey, strategy, universe, verdict]
  );

  const [selectedValidation, setSelectedValidation] = useState(null);

  if (loading) return <LoadingState rows={10} />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const results = data?.results || [];
  if (results.length === 0) return <EmptyState message="No validations found matching filters" />;

  return (
    <div className="space-y-6">
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-white/[0.02] border-b border-[--glass-border] text-[--text-muted] text-[10px] uppercase tracking-widest font-bold">
              <th className="text-left py-4 px-4">Strategy</th>
              <th className="text-left py-4 px-4">Asset</th>
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
              
              return (
                <tr
                  key={`${r.strategy}-${r.symbol}-${idx}`}
                  className={`border-b border-white/5 hover:bg-white/[0.04] transition-colors cursor-pointer group ${
                    isSelected ? 'bg-green-500/[0.05] border-green-500/20' : ''
                  }`}
                  onClick={() => setSelectedValidation(r)}
                >
                  <td className="py-4 px-4">
                    <span className="text-white font-medium">{r.strategy.split('_')[0].toUpperCase()}</span>
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
                    {r.sharpe.toFixed(2)}
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
