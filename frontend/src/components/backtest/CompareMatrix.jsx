import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPF, VERDICT_COLORS, getAssetType } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import { ChevronUp, ChevronDown, Info, ShieldCheck, AlertTriangle, Filter, Activity, Target } from 'lucide-react';

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
    
    let assets = data.assets.map(symbol => {
      const strats = data.matrix[symbol] || {};
      const allStrats = Object.values(strats);
      const validStrats = allStrats.filter(s => s.verdict === 'VALIDATED');
      
      const avgPf = validStrats.length > 0 
        ? validStrats.reduce((sum, s) => sum + s.pf, 0) / validStrats.length 
        : 0;
      
      const totalTrades = allStrats.reduce((sum, s) => sum + (s.n_trades || 0), 0);
      const avgWr = allStrats.length > 0
        ? allStrats.reduce((sum, s) => sum + (s.win_rate || 0), 0) / allStrats.length
        : 0;
      
      const assetType = getAssetType(symbol);
      
      return { 
        symbol, 
        score: validStrats.length + (avgPf / 10),
        avgPf,
        validCount: validStrats.length,
        totalTrades,
        avgWr,
        type: assetType
      };
    });

    if (assetTypeFilter) {
      assets = assets.filter(a => a.type.label.toUpperCase().includes(assetTypeFilter.toUpperCase()));
    }

    return assets.sort((a, b) => {
      let aVal, bVal;
      if (sortConfig.key === 'symbol') {
        aVal = a.symbol; bVal = b.symbol;
      } else if (sortConfig.key === 'score') {
        aVal = a.score; bVal = b.score;
      } else if (sortConfig.key === 'trades') {
        aVal = a.totalTrades; bVal = b.totalTrades;
      } else if (sortConfig.key === 'wr') {
        aVal = a.avgWr; bVal = b.avgWr;
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

  return (
    <div className="space-y-0 relative">
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
        subtitle="Robustesse croisée et performance agrégée par actif"
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
                <th className="text-right py-4 px-4 border-b border-[--glass-border] cursor-pointer hover:text-white" onClick={() => setSortConfig({ key: 'trades', direction: sortConfig.direction === 'asc' ? 'desc' : 'asc' })} title="Total des trades sur toutes les stratégies">
                  <div className="flex items-center justify-end gap-1"><Activity size={10} /> Activité</div>
                </th>
                <th className="text-right py-4 px-4 border-b border-[--glass-border] cursor-pointer hover:text-white" onClick={() => setSortConfig({ key: 'wr', direction: sortConfig.direction === 'asc' ? 'desc' : 'asc' })} title="Win Rate moyen toutes stratégies confondues">
                  <div className="flex items-center justify-end gap-1"><Target size={10} /> Précision</div>
                </th>
                {strategies.map((s) => (
                  <th key={s} className="text-center py-4 px-4 border-b border-[--glass-border] cursor-pointer hover:text-white" onClick={() => setSortConfig({ key: s, direction: sortConfig.direction === 'asc' ? 'desc' : 'asc' })}>
                    {s.split('_')[0]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedAssets.map(({ symbol, validCount, type, totalTrades, avgWr }) => (
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
                  <td className="py-4 px-4 text-right tabular-nums font-medium text-[--text-secondary]">
                    {totalTrades}
                  </td>
                  <td className={`py-4 px-4 text-right tabular-nums font-bold ${avgWr >= 0.6 ? 'text-green-400' : 'text-[--text-muted]'}`}>
                    {(avgWr * 100).toFixed(0)}%
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
        
        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6 bg-white/[0.01] border-t border-white/5">
          <div className="space-y-2">
            <h5 className="text-[10px] font-bold uppercase tracking-widest text-white flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              Heatmap PF
            </h5>
            <p className="text-[10px] text-[--text-muted] leading-relaxed">
              L'intensité du vert représente le Profit Factor. Les cases grisées indiquent un échec de robustesse (REJECTED).
            </p>
          </div>
          <div className="space-y-2">
            <h5 className="text-[10px] font-bold uppercase tracking-widest text-white flex items-center gap-2">
              <Activity size={12} className="text-blue-400" />
              Activité & Précision
            </h5>
            <p className="text-[10px] text-[--text-muted] leading-relaxed">
              L'activité est le cumul des trades historiques. La précision est le taux de succès moyen.
            </p>
          </div>
          <div className="space-y-2">
            <h5 className="text-[10px] font-bold uppercase tracking-widest text-white flex items-center gap-2">
              <ShieldCheck size={12} className="text-green-400" />
              Confiance
            </h5>
            <p className="text-[10px] text-[--text-muted] leading-relaxed">
              Nombre de stratégies où l'actif est pleinement <strong>VALIDATED</strong>.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
