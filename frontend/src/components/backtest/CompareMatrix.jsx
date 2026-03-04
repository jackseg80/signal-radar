import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPF, VERDICT_COLORS, getAssetType, ASSET_TYPES } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import { ChevronUp, ChevronDown, Info, ShieldCheck, AlertTriangle, Filter } from 'lucide-react';

const getHeatmapColor = (pf, verdict) => {
  if (!pf || pf <= 0) return 'bg-white/[0.02] text-[--text-muted]';
  
  let colorClass = 'bg-red-500/20';
  if (pf >= 1.0) colorClass = 'bg-amber-500/20';
  if (pf >= 1.2) colorClass = 'bg-green-500/20';
  if (pf >= 1.5) colorClass = 'bg-green-500/40';
  if (pf >= 2.0) colorClass = 'bg-green-500/70';

  if (verdict === 'REJECTED') {
    return 'bg-slate-500/10 text-slate-500 grayscale opacity-40';
  }
  
  if (verdict === 'CONDITIONAL') {
    return `${colorClass} opacity-70`;
  }

  return `${colorClass} text-white font-bold border-b-2 border-green-400/30`;
};

export default function CompareMatrix() {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.compare(), [refreshKey]);
  const [sortConfig, setSortConfig] = useState({ key: 'score', direction: 'desc' });
  const [assetTypeFilter, setAssetTypeFilter] = useState('');

  const filteredAndSortedAssets = useMemo(() => {
    if (!data?.assets) return [];
    
    // 1. Calculate scores and types
    let assets = data.assets.map(symbol => {
      const strats = data.matrix[symbol] || {};
      const validStrats = Object.values(strats).filter(s => s.verdict === 'VALIDATED');
      const avgPf = validStrats.length > 0 
        ? validStrats.reduce((sum, s) => sum + s.pf, 0) / validStrats.length 
        : 0;
      
      const assetType = getAssetType(symbol);
      
      return { 
        symbol, 
        score: validStrats.length + (avgPf / 10),
        avgPf,
        validCount: validStrats.length,
        type: assetType
      };
    });

    // 2. Filter by type
    if (assetTypeFilter) {
      assets = assets.filter(a => a.type.label.toUpperCase().includes(assetTypeFilter.toUpperCase()));
    }

    // 3. Sort
    return assets.sort((a, b) => {
      let aVal, bVal;
      if (sortConfig.key === 'symbol') {
        aVal = a.symbol; bVal = b.symbol;
      } else if (sortConfig.key === 'score') {
        aVal = a.score; bVal = b.score;
      } else {
        aVal = data.matrix[a.symbol]?.[sortConfig.key]?.pf || 0;
        bVal = data.matrix[b.symbol]?.[sortConfig.key]?.pf || 0;
      }

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig, assetTypeFilter]);

  if (loading) return <Card title="Matrice de Confiance"><LoadingState rows={10} /></Card>;
  if (error) return <Card title="Matrice de Confiance"><ErrorState message={error} onRetry={refetch} /></Card>;

  const strategies = data?.strategies || [];
  const stickyTop = "top-[124px]"; // Just below tabs

  return (
    <div className="space-y-0 relative">
      {/* Mini filter bar for matrix */}
      <div className="sticky top-[124px] z-[35] bg-[--bg-primary] pb-4">
        <div className="flex items-center gap-4 p-3 bg-white/[0.02] border border-white/5 rounded-xl backdrop-blur-md">
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-[--text-muted]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[--text-muted]">Type :</span>
          </div>
          <select 
            value={assetTypeFilter} 
            onChange={(e) => setAssetTypeFilter(e.target.value)}
            className="bg-[#1a1d27] border border-white/10 rounded-lg px-3 py-1 text-xs text-white outline-none focus:border-green-500/50 cursor-pointer min-w-[120px]"
          >
            <option value="">Tous les Types</option>
            <option value="Stock">Stocks</option>
            <option value="ETF">ETFs</option>
            <option value="Forex">Forex</option>
          </select>
          <div className="flex-1" />
          <div className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest bg-white/5 px-3 py-1 rounded-lg border border-white/5">
            {filteredAndSortedAssets.length} Actifs analysés
          </div>
        </div>
      </div>

      <Card 
        title="Matrice de Confiance Stratégique" 
        subtitle="Visualisation de la robustesse croisée par actif"
        noPadding
        noScroll
      >
        <div className="overflow-visible">
          <table className="w-full text-sm border-separate border-spacing-0">
            <thead className="sticky top-[188px] z-[30] bg-[#1a1d27]">
              <tr className="text-[--text-muted] text-[10px] uppercase tracking-widest font-bold shadow-sm">
                <th className="text-left py-4 px-6 border-b border-[--glass-border] cursor-pointer hover:text-white" onClick={() => setSortConfig({ key: 'symbol', direction: sortConfig.direction === 'asc' ? 'desc' : 'asc' })}>
                  Actif
                </th>
                <th className="text-center py-4 px-4 border-b border-[--glass-border] cursor-pointer hover:text-white" onClick={() => setSortConfig({ key: 'score', direction: sortConfig.direction === 'asc' ? 'desc' : 'asc' })}>
                  Confiance
                </th>
                {strategies.map((s) => (
                  <th key={s} className="text-center py-4 px-4 border-b border-[--glass-border] cursor-pointer hover:text-white" onClick={() => setSortConfig({ key: s, direction: sortConfig.direction === 'asc' ? 'desc' : 'asc' })}>
                    {s.split('_')[0]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedAssets.map(({ symbol, validCount, type }) => (
                <tr key={symbol} className="border-b border-white/5 hover:bg-white/[0.02] transition-all group">
                  <td className="py-4 px-6">
                    <div className="flex flex-col">
                      <span className="font-bold text-white group-hover:text-green-400 transition-colors">{symbol}</span>
                      <span className={`w-fit text-[7px] font-black px-1 rounded ${type.bg} ${type.text} border ${type.border} uppercase mt-0.5`}>
                        {type.label}
                      </span>
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <div className="flex justify-center gap-1">
                      {[...Array(3)].map((_, i) => (
                        <ShieldCheck 
                          key={i} 
                          size={12} 
                          className={i < validCount ? 'text-green-400' : 'text-white/5'} 
                        />
                      ))}
                    </div>
                  </td>
                  {strategies.map((strat) => {
                    const val = data.matrix[symbol]?.[strat];
                    const pf = val?.pf || 0;
                    const verdict = val?.verdict || 'NONE';
                    
                    return (
                      <td key={strat} className="p-1">
                        <div 
                          className={`h-12 flex flex-col items-center justify-center rounded-lg transition-all ${getHeatmapColor(pf, verdict)}`}
                          title={`${symbol} ${strat}: PF ${pf.toFixed(2)} (${verdict})`}
                        >
                          <span className="text-xs tabular-nums">{pf > 0 ? pf.toFixed(2) : '--'}</span>
                          {verdict === 'REJECTED' && <AlertTriangle size={8} className="mt-1" />}
                          {verdict === 'VALIDATED' && <div className="w-1 h-1 rounded-full bg-white/50 mt-1" />}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 bg-white/[0.01] border-t border-white/5">
          <div className="space-y-2">
            <h5 className="text-[10px] font-bold uppercase tracking-widest text-white flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              Lecture de la Matrice
            </h5>
            <p className="text-[10px] text-[--text-muted] leading-relaxed">
              Les cases <strong>lumineuses</strong> indiquent une performance robuste (VALIDATED). 
              Les cases <strong>grisées</strong> indiquent une performance "trompeuse" (REJECTED) : 
              le Profit Factor peut être élevé, mais il n'a pas passé les tests de stabilité ou de robustesse.
            </p>
          </div>
          <div className="space-y-2">
            <h5 className="text-[10px] font-bold uppercase tracking-widest text-white flex items-center gap-2">
              <ShieldCheck size={12} className="text-green-400" />
              Score de Confiance
            </h5>
            <p className="text-[10px] text-[--text-muted] leading-relaxed">
              Plus un actif a de boucliers, plus il est validé sur un grand nombre de stratégies différentes. 
              C'est un excellent indicateur pour la diversification de votre portefeuille.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
