import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, SIGNAL_COLORS, STRATEGY_COLORS, STRATEGY_LABELS, getAssetType } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import { Table, ChevronUp, ChevronDown, Info } from 'lucide-react';

const STRATEGY_ORDER = ['rsi2', 'ibs', 'tom'];

const STRATEGY_TOOLTIPS = {
  rsi2: "RSI(2) : Mesure la force relative sur 2 jours. < 10 (vert) = Survendu, opportunité d'achat. < 20 (jaune) = Proche du signal.",
  ibs: "IBS (Internal Bar Strength) : Position du prix dans le range du jour. < 0.2 (vert) = Clôture très basse, rebond probable.",
  tom: "TOM (Turn Of Month) : Anomalie de fin/début de mois. Indique le nombre de jours de bourse restants avant la fin du mois.",
};

function ProximityBar({ proximity, strategy }) {
  if (!proximity || proximity.pct == null) return null;

  const pct = proximity.pct;
  const barColor = pct >= 75
    ? 'var(--accent-green)'
    : pct >= 50
      ? 'var(--accent-amber)'
      : 'var(--text-muted)';

  const trendBlocked = proximity.trend_ok === false;
  
  const tooltip = trendBlocked 
    ? "Tendance bloquée (SMA200) : Pas de signal possible." 
    : `${pct}% de proximité avec le seuil d'achat.`;

  return (
    <div 
      className={`mt-1 flex items-center gap-2 justify-center ${trendBlocked ? 'opacity-40' : ''}`}
      title={tooltip}
    >
      <div className="w-16 h-1 rounded-full bg-white/5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${pct}%`, backgroundColor: barColor }}
        />
      </div>
      <span className="text-[10px] text-[--text-muted] tabular-nums whitespace-nowrap font-medium">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

export default function MarketOverview({ className, onSymbolClick }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.marketOverview(), [refreshKey]);
  
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
    
    const assets = [...data.assets];
    return assets.sort((a, b) => {
      let aVal, bVal;

      if (sortConfig.key === 'symbol') {
        aVal = a.symbol;
        bVal = b.symbol;
      } else if (sortConfig.key === 'price') {
        aVal = a.close;
        bVal = b.close;
      } else if (sortConfig.key === 'positions') {
        aVal = a.has_open_position ? 1 : 0;
        bVal = b.has_open_position ? 1 : 0;
      } else if (STRATEGY_ORDER.includes(sortConfig.key)) {
        aVal = a.strategies[sortConfig.key]?.indicator_value ?? -Infinity;
        bVal = b.strategies[sortConfig.key]?.indicator_value ?? -Infinity;
      }

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  if (loading) return <Card title="Market Overview" className={className}><LoadingState rows={8} /></Card>;
  if (error) return <Card title="Market Overview" className={className}><ErrorState message={error} onRetry={refetch} /></Card>;

  if (sortedAssets.length === 0) {
    return <Card title="Market Overview" className={className}><EmptyState message="No market data" /></Card>;
  }

  const activeStrategies = STRATEGY_ORDER.filter((s) =>
    data.assets.some((a) => a.strategies[s])
  );

  return (
    <Card 
      title="Market Overview" 
      subtitle="Full universe status & indicator proximity"
      headerAction={<Table size={14} className="text-[--text-muted]" />}
      noPadding
      className={className}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-white/[0.02] border-b border-[--glass-border] text-[--text-muted] text-[10px] uppercase tracking-widest font-bold">
              <th className="text-left py-4 px-6 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('symbol')}>
                <div className="flex items-center gap-1">Asset {getSortIcon('symbol')}</div>
              </th>
              <th className="text-right py-4 px-4 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('price')}>
                <div className="flex items-center justify-end gap-1">Price {getSortIcon('price')}</div>
              </th>
              {activeStrategies.map((s) => {
                const sc = STRATEGY_COLORS[s] || STRATEGY_COLORS.rsi2;
                return (
                  <th key={s} className="text-center py-4 px-4 cursor-pointer hover:text-white transition-colors group/header" onClick={() => requestSort(s)} title={STRATEGY_TOOLTIPS[s]}>
                    <div className="flex flex-col items-center">
                      <div className="flex items-center gap-1">
                        <span className={`${sc.text}`}>{STRATEGY_LABELS[s] || s}</span>
                        {getSortIcon(s)}
                        <Info size={10} className="opacity-0 group-hover/header:opacity-50 transition-opacity ml-1" />
                      </div>
                    </div>
                  </th>
                );
              })}
              <th className="text-center py-4 px-6 cursor-pointer hover:text-white transition-colors" onClick={() => requestSort('positions')}>
                <div className="flex items-center justify-center gap-1">Positions {getSortIcon('positions')}</div>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedAssets.map((a) => {
              const assetType = getAssetType(a.symbol);
              return (
                <tr
                  key={a.symbol}
                  className={`border-b border-white/5 hover:bg-white/[0.04] transition-all duration-200 group ${
                    a.has_open_position ? 'bg-green-500/[0.03]' : ''
                  }`}
                >
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3 cursor-pointer" onClick={() => onSymbolClick && onSymbolClick(a.symbol)}>
                      <div className="flex flex-col">
                        <span className="font-bold text-white group-hover:text-green-400 transition-colors">{a.symbol}</span>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[7px] font-black px-1 rounded ${assetType.bg} ${assetType.text} border ${assetType.border} uppercase`}>
                            {assetType.label}
                          </span>
                          <span className="text-[10px] text-[--text-muted]">Daily OHLCV</span>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-right tabular-nums font-medium text-[--text-secondary]">
                    {formatPrice(a.close)}
                  </td>
                  {activeStrategies.map((s) => {
                    const strat = a.strategies[s];
                    if (!strat || strat.signal == null) {
                      return <td key={s} className="py-4 px-4 text-center text-[--text-muted] opacity-30">--</td>;
                    }
                    const sig = SIGNAL_COLORS[strat.signal] || SIGNAL_COLORS.NO_SIGNAL;

                    let barPct = 0;
                    let barColor = 'var(--text-muted)';
                    let valueTooltip = "";

                    if (s === 'rsi2' && strat.indicator_value != null) {
                      barPct = Math.max(0, Math.min(100, (1 - strat.indicator_value / 30) * 100));
                      barColor = strat.indicator_value < 10 ? 'var(--accent-green)' : strat.indicator_value < 20 ? 'var(--accent-amber)' : 'var(--text-muted)';
                      valueTooltip = `Valeur RSI(2). < 10 est la zone d'achat idéale.`;
                    } else if (s === 'ibs' && strat.indicator_value != null) {
                      barPct = Math.max(0, Math.min(100, (1 - strat.indicator_value / 0.5) * 100));
                      barColor = strat.indicator_value < 0.2 ? 'var(--accent-green)' : strat.indicator_value < 0.35 ? 'var(--accent-amber)' : 'var(--text-muted)';
                      valueTooltip = `Valeur IBS. < 0.2 est la zone d'achat idéale.`;
                    } else if (s === 'tom') {
                      valueTooltip = `Jours restants avant la fin du mois.`;
                    }

                    return (
                      <td key={s} className="py-4 px-4">
                        <div className="flex flex-col items-center gap-1.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${sig.bg} ${sig.text}`} title={strat.signal === 'SKIP' ? "SKIP : Condition de tendance non remplie." : ""}>
                            {strat.signal === 'NO_SIGNAL' ? '--' : strat.signal}
                          </span>
                          
                          {strat.indicator_value != null && (
                            <div className="flex flex-col items-center" title={valueTooltip}>
                              <span className="text-[10px] text-[--text-secondary] tabular-nums font-medium">
                                {Number(strat.indicator_value).toFixed(s === 'ibs' ? 2 : s === 'rsi2' ? 1 : 0)}
                              </span>
                              {(s === 'rsi2' || s === 'ibs') && (
                                <div className="w-10 h-1 rounded-full bg-white/5 overflow-hidden mt-0.5">
                                  <div className="h-full rounded-full transition-all duration-700" style={{ width: `${barPct}%`, backgroundColor: barColor }} />
                                </div>
                              )}
                            </div>
                          )}
                          {strat.proximity?.near && <ProximityBar proximity={strat.proximity} strategy={s} />}
                        </div>
                      </td>
                    );
                  })}
                  <td className="py-4 px-6 text-center">
                    {a.has_open_position ? (
                      <div className="flex flex-col items-center gap-1">
                        <span className="text-green-400 text-[10px] font-bold uppercase tracking-widest bg-green-500/10 px-2 py-0.5 rounded-full border border-green-500/20">OPEN</span>
                        <div className="flex gap-1 justify-center">
                          {a.position_strategies.map((s) => {
                            const sc = STRATEGY_COLORS[s] || STRATEGY_COLORS.rsi2;
                            return <span key={s} className={`text-[8px] uppercase font-bold ${sc.text}`}>{STRATEGY_LABELS[s] || s}</span>;
                          })}
                        </div>
                      </div>
                    ) : (
                      <span className="text-[--text-muted] opacity-20">--</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
