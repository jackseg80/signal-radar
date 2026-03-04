import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPF, VERDICT_COLORS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import { ChevronUp, ChevronDown, Info } from 'lucide-react';

const VERDICT_EXPLANATIONS = {
  VALIDATED: "Robuste, stable sur toutes les périodes et statistiquement significatif.",
  CONDITIONAL: "Robuste, mais manque soit de stabilité temporelle, soit de volume de trades suffisant.",
  REJECTED: "Échec aux tests de robustesse ou de stabilité. Performance probablement due au hasard (Overfitting)."
};

export default function CompareMatrix() {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.compare(), [refreshKey]);
  const [sortConfig, setSortConfig] = useState({ key: 'symbol', direction: 'asc' });

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

  const sortedAssets = useMemo(() => {
    if (!data?.assets) return [];
    
    return [...data.assets].sort((a, b) => {
      let aVal, bVal;
      
      if (sortConfig.key === 'symbol') {
        aVal = a;
        bVal = b;
      } else {
        aVal = data.matrix[a]?.[sortConfig.key]?.pf || 0;
        bVal = data.matrix[b]?.[sortConfig.key]?.pf || 0;
      }

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  if (loading) return <Card title="Cross-Strategy Comparison"><LoadingState rows={10} /></Card>;
  if (error) return <Card title="Cross-Strategy Comparison"><ErrorState message={error} onRetry={refetch} /></Card>;

  const assets = sortedAssets;
  const strategies = data?.strategies || [];

  if (assets.length === 0) {
    return <Card title="Cross-Strategy Comparison"><EmptyState message="No comparisons available" /></Card>;
  }

  return (
    <Card 
      title="Cross-Strategy Comparison" 
      subtitle="Comparaison du Profit Factor par actif et stratégie"
      noPadding
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-white/[0.02] border-b border-[--glass-border] text-[--text-muted] text-[10px] uppercase tracking-widest font-bold">
              <th className="text-left py-4 px-6 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('symbol')}>
                <div className="flex items-center gap-1">Asset {getSortIcon('symbol')}</div>
              </th>
              {strategies.map((s) => (
                <th key={s} className="text-center py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort(s)}>
                  <div className="flex items-center justify-center gap-1">
                    {s.split('_')[0]} {getSortIcon(s)}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {assets.map((asset) => (
              <tr key={asset} className="border-b border-white/5 hover:bg-white/[0.04] transition-all duration-200 group">
                <td className="py-4 px-6 font-bold text-white group-hover:text-green-400 transition-colors">
                  {asset}
                </td>
                {strategies.map((strat) => {
                  const val = data.matrix[asset]?.[strat];
                  if (!val) return <td key={strat} className="py-4 px-4 text-center text-[--text-muted] opacity-20">--</td>;
                  
                  const pf = val.pf;
                  const verdict = val.verdict;
                  const v = VERDICT_COLORS[verdict] || VERDICT_COLORS.REJECTED;
                  
                  return (
                    <td key={strat} className="py-4 px-4 text-center">
                      <div className="flex flex-col items-center gap-1 group/item relative">
                        <span className={`text-sm font-bold tabular-nums ${pf >= 1.5 ? 'text-green-400' : pf >= 1 ? 'text-white' : 'text-red-400'}`}>
                          {formatPF(pf)}
                        </span>
                        <div 
                          className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${v.text} ${v.bg} border ${v.border} cursor-help flex items-center gap-1`}
                          title={VERDICT_EXPLANATIONS[verdict]}
                        >
                          {verdict}
                          <Info size={8} />
                        </div>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="p-4 bg-blue-500/5 border-t border-white/5 flex gap-3">
        <Info size={16} className="text-blue-400 shrink-0 mt-0.5" />
        <p className="text-[10px] text-[--text-muted] leading-relaxed">
          <strong>Note :</strong> Un Profit Factor élevé ne garantit pas la validation. Le système exige que la stratégie soit 
          stable dans le temps et robuste face aux changements de paramètres pour éliminer le hasard.
        </p>
      </div>
    </Card>
  );
}
