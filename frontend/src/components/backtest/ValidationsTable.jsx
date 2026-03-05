import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { VERDICT_COLORS, STRATEGY_LABELS, getAssetType } from '../../utils/format';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import RobustnessHeatmap from './RobustnessHeatmap';
import AssetDetailPanel from './AssetDetailPanel';
import AssetIcon from '../ui/AssetIcon';
import { X, Filter, ChevronUp, ChevronDown, Info, ShieldCheck, Activity } from 'lucide-react';

const STRATEGY_MAPPING = {
  'rsi2': 'rsi2_mean_reversion',
  'ibs': 'ibs_mean_reversion',
  'tom': 'turn_of_month'
};

const COLUMN_TOOLTIPS = {
  trades: "Nombre total de transactions effectuées durant la période de test (Out-of-Sample).",
  wr: "Win Rate : Pourcentage de trades gagnants sur le total.",
  pf: "Profit Factor : Somme des gains / Somme des pertes. > 1.0 est profitable, > 1.5 est excellent.",
  sharpe: "Ratio de Sharpe : Mesure de la rentabilité par rapport au risque (volatilité).",
  robust: "Pourcentage de combinaisons de paramètres (ex: RSI 2,3,4) qui restent profitables.",
  verdict: "Sceau final de qualité basé sur la robustesse, la stabilité et la significativité statistique."
};

export default function ValidationsTable() {
  const { refreshKey } = useRefresh();
  const [filters, setFilters] = useState({
    strategy: '',
    universe: '',
    verdict: '',
    assetType: ''
  });
  const [sortConfig, setSortConfig] = useState({ key: 'profit_factor', direction: 'desc' });

  const { data, loading, error, refetch } = useApi(
    () => api.validations({ 
      strategy: STRATEGY_MAPPING[filters.strategy] || undefined, 
      universe: filters.universe || undefined, 
      verdict: filters.verdict || undefined 
    }),
    [refreshKey, filters.strategy, filters.universe, filters.verdict]
  );

  const [selectedValidation, setSelectedValidation] = useState(null);
  const [selectedAsset, setSelectedAsset] = useState(null);

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

  const filteredResults = useMemo(() => {
    let results = data?.results || [];
    
    if (filters.assetType) {
      results = results.filter(r => getAssetType(r.symbol, r.universe).label.toUpperCase().includes(filters.assetType.toUpperCase()));
    }
    
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
  }, [data, sortConfig, filters.assetType]);

  const allStrategies = ['rsi2', 'ibs', 'tom'];
  const allUniverses = useMemo(() => {
    if (!data?.results?.length) return [];
    return [...new Set(data.results.map(r => r.universe))].filter(Boolean).sort();
  }, [data]);

  if (loading && !filteredResults.length) return <LoadingState rows={10} />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  const selectClass = "bg-[#1a1d27] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-green-500/50 cursor-pointer appearance-none min-w-[140px]";

  const filterStickyTop = "top-[132px]";

  return (
    <div className="space-y-0 relative">
      <div className={`sticky ${filterStickyTop} z-[35] bg-[--bg-primary] pb-4`}>
        <div className="flex flex-wrap gap-4 p-4 bg-white/[0.02] border border-white/5 rounded-xl items-center shadow-2xl backdrop-blur-md">
          <div className="flex items-center gap-2 mr-2">
            <Filter size={14} className="text-[--text-muted]" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-[--text-muted]">Filtrer :</span>
          </div>
          
          <select value={filters.strategy} onChange={(e) => setFilters({ ...filters, strategy: e.target.value })} className={selectClass}>
            <option value="">Toutes Stratégies</option>
            {allStrategies.map(s => <option key={s} value={s}>{STRATEGY_LABELS[s] || s}</option>)}
          </select>

          <select value={filters.assetType} onChange={(e) => setFilters({ ...filters, assetType: e.target.value })} className={selectClass}>
            <option value="">Tous Types</option>
            <option value="Stock">Stocks</option>
            <option value="ETF">ETFs</option>
            <option value="Forex">Forex</option>
          </select>

          <select value={filters.verdict} onChange={(e) => setFilters({ ...filters, verdict: e.target.value })} className={selectClass}>
            <option value="">Tous Verdicts</option>
            <option value="VALIDATED">VALIDATED</option>
            <option value="CONDITIONAL">CONDITIONAL</option>
            <option value="REJECTED">REJECTED</option>
          </select>

          {allUniverses.length > 0 && (
            <select value={filters.universe} onChange={(e) => setFilters({ ...filters, universe: e.target.value })} className={selectClass}>
              <option value="">Tous Univers</option>
              {allUniverses.map(u => <option key={u} value={u}>{u}</option>)}
            </select>
          )}

          <div className="flex-1" />
          <div className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest bg-white/5 px-3 py-1 rounded-lg border border-white/5">
            {filteredResults.length} Tests affichés
          </div>
        </div>
      </div>

      {filteredResults.length === 0 ? (
        <div className="pt-8"><EmptyState message="Aucun test ne correspond à ces critères." /></div>
      ) : (
        <div className="overflow-visible">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-[200px] z-[20]">
              <tr className="bg-[#1a1d27] border-b border-[--glass-border] text-[--text-muted] text-[10px] uppercase tracking-widest font-bold shadow-sm">
                <th className="text-left py-4 px-4 cursor-pointer hover:text-white" onClick={() => requestSort('symbol')}>
                  <div className="flex items-center gap-1">Actif {getSortIcon('symbol')}</div>
                </th>
                <th className="text-left py-4 px-4 cursor-pointer hover:text-white" onClick={() => requestSort('strategy')}>
                  <div className="flex items-center gap-1">Stratégie {getSortIcon('strategy')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white group/h" onClick={() => requestSort('n_trades')} title={COLUMN_TOOLTIPS.trades}>
                  <div className="flex items-center justify-end gap-1">Trades <Info size={10} className="opacity-30 group-hover/h:opacity-100" /> {getSortIcon('n_trades')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white group/h" onClick={() => requestSort('win_rate')} title={COLUMN_TOOLTIPS.wr}>
                  <div className="flex items-center justify-end gap-1">Win Rate <Info size={10} className="opacity-30 group-hover/h:opacity-100" /> {getSortIcon('win_rate')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white group/h" onClick={() => requestSort('profit_factor')} title={COLUMN_TOOLTIPS.pf}>
                  <div className="flex items-center justify-end gap-1 text-green-400">PF <Info size={10} className="opacity-30 group-hover/h:opacity-100" /> {getSortIcon('profit_factor')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white group/h" onClick={() => requestSort('sharpe')} title={COLUMN_TOOLTIPS.sharpe}>
                  <div className="flex items-center justify-end gap-1">Sharpe <Info size={10} className="opacity-30 group-hover/h:opacity-100" /> {getSortIcon('sharpe')}</div>
                </th>
                <th className="text-right py-4 px-4 cursor-pointer hover:text-white group/h" onClick={() => requestSort('robustness_pct')} title={COLUMN_TOOLTIPS.robust}>
                  <div className="flex items-center justify-end gap-1">Robust% <Info size={10} className="opacity-30 group-hover/h:opacity-100" /> {getSortIcon('robustness_pct')}</div>
                </th>
                <th className="text-center py-4 px-4 cursor-pointer hover:text-white group/h" onClick={() => requestSort('verdict')} title={COLUMN_TOOLTIPS.verdict}>
                  <div className="flex items-center justify-center gap-1">Verdict <Info size={10} className="opacity-30 group-hover/h:opacity-100" /> {getSortIcon('verdict')}</div>
                </th>
              </tr>
            </thead>
            <tbody className="bg-[--bg-primary]">
              {filteredResults.map((r, idx) => {
                const v = VERDICT_COLORS[r.verdict] || VERDICT_COLORS.REJECTED;
                const isSelected = selectedValidation?.symbol === r.symbol && selectedValidation?.strategy === r.strategy;
                const baseStrategy = r.strategy.split('_')[0];
                const assetType = getAssetType(r.symbol, r.universe);
                
                return (
                  <tr
                    key={`${r.strategy}-${r.symbol}-${idx}`}
                    className={`border-b border-white/5 hover:bg-white/[0.04] transition-all cursor-pointer group ${
                      isSelected ? 'bg-green-500/[0.05] border-green-500/20' : ''
                    }`}
                    onClick={() => {
                      setSelectedValidation(r);
                      setSelectedAsset({
                        symbol: r.symbol,
                        strategy: r.strategy.split('_')[0]
                      });
                    }}
                  >
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-3">
                        <AssetIcon symbol={r.symbol} size="sm" />
                        <div className="flex flex-col">
                          <span className="text-white font-bold group-hover:text-green-400 transition-colors text-base">{r.symbol}</span>
                          <span className={`w-fit text-[7px] font-black px-1 rounded ${assetType.bg} ${assetType.text} border ${assetType.border} uppercase mt-0.5`}>
                            {assetType.label}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest bg-white/5 text-[--text-muted]`}>
                        {STRATEGY_LABELS[baseStrategy] || baseStrategy}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right tabular-nums text-[--text-secondary] font-medium">{r.n_trades}</td>
                    <td className="py-4 px-4 text-right tabular-nums text-[--text-secondary]">{(r.win_rate * 100).toFixed(0)}%</td>
                    <td className="py-4 px-4 text-right tabular-nums">
                       <div className="flex flex-col items-end gap-1">
                          <span className={`font-bold ${r.profit_factor >= 1.5 ? 'text-green-400' : r.profit_factor >= 1 ? 'text-white' : 'text-red-400'}`}>{r.profit_factor.toFixed(2)}</span>
                          <div className="w-12 h-1 bg-white/5 rounded-full overflow-hidden">
                             <div className={`h-full ${r.profit_factor >= 1.5 ? 'bg-green-500' : 'bg-amber-500'}`} style={{ width: `${Math.min(100, (r.profit_factor / 3) * 100)}%` }} />
                          </div>
                       </div>
                    </td>
                    <td className={`py-4 px-4 text-right tabular-nums font-medium ${r.sharpe >= 2 ? 'text-blue-400' : 'text-[--text-secondary]'}`}>{r.sharpe ? r.sharpe.toFixed(2) : '--'}</td>
                    <td className="py-4 px-4 text-right tabular-nums">
                      <div className="flex flex-col items-end gap-1">
                        <span className={`font-bold ${r.robustness_pct >= 80 ? 'text-green-400' : 'text-amber-400'}`}>{r.robustness_pct.toFixed(0)}%</span>
                        <div className="w-12 h-1 bg-white/5 rounded-full overflow-hidden">
                          <div 
                            className={`h-full ${r.robustness_pct >= 80 ? 'bg-green-500' : 'bg-amber-500'}`}
                            style={{ width: `${r.robustness_pct}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-4 text-center">
                      <div className="flex flex-col items-center gap-1">
                        <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-tighter border ${v.bg} ${v.text} ${v.border} shadow-sm`}>{r.verdict}</span>
                        {r.verdict === 'VALIDATED' && <ShieldCheck size={10} className="text-green-400" />}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selectedAsset && (
        <AssetDetailPanel
          symbol={selectedAsset.symbol}
          initialStrategy={selectedAsset.strategy}
          matrixData={{ [selectedAsset.symbol]: { [selectedAsset.strategy]: true } }}
          onClose={() => setSelectedAsset(null)}
        />
      )}

      {selectedValidation && (
        <div className="animate-fade-in relative mt-8 pb-20">
          <div className="glass-card rounded-2xl border border-green-500/20 overflow-hidden shadow-2xl">
            <div className="p-4 bg-green-500/10 border-b border-green-500/20 flex justify-between items-center">
               <div className="flex items-center gap-3">
                  <Activity size={18} className="text-green-400" />
                  <div>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">Robustesse Paramétrique : {selectedValidation.symbol}</h3>
                    <p className="text-[10px] text-green-400/70 font-medium">Analyse des 48 variantes</p>
                  </div>
               </div>
               <button onClick={() => setSelectedValidation(null)} className="p-2 rounded-full hover:bg-white/10 text-white transition-colors cursor-pointer"><X size={20} /></button>
            </div>
            <div className="p-6">
              <RobustnessHeatmap strategy={selectedValidation.strategy.split('_')[0]} symbol={selectedValidation.symbol} universe={selectedValidation.universe} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
