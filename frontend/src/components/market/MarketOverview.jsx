import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, SIGNAL_COLORS, STRATEGY_COLORS, STRATEGY_LABELS, getAssetType } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import AssetIcon from '../ui/AssetIcon';
import { Table, ChevronUp, ChevronDown, Info } from 'lucide-react';

const STRATEGY_ORDER = ['rsi2', 'ibs', 'tom'];

const STRATEGY_TOOLTIPS = {
  rsi2: "RSI(2) : Mesure la force relative sur 2 jours. < 10 (vert) = Survendu, opportunité d'achat. < 20 (jaune) = Proche du signal.",
  ibs: "IBS (Internal Bar Strength) : Position du prix dans le range du jour. < 0.2 (vert) = Clôture très basse ; seuil technique de la stratégie.",
  tom: "TOM (Turn Of Month) : Anomalie de fin/début de mois. Indique le nombre de jours de bourse restants avant la fin du mois.",
};

function ProximityBar({ proximity }) {
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
      } else if (STRATEGY_ORDER.includes(sortConfig.key)) {
        aVal = a.strategies?.[sortConfig.key]?.indicator_value ?? -Infinity;
        bVal = b.strategies?.[sortConfig.key]?.indicator_value ?? -Infinity;
      }

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  if (loading) return <Card title="Vue d’ensemble des actions" className={className}><LoadingState rows={8} /></Card>;
  if (error) return <Card title="Vue d’ensemble des actions" className={className}><ErrorState message={error} onRetry={refetch} /></Card>;

  if (!data?.assets || data.assets.length === 0) {
    return <Card title="Vue d’ensemble des actions" className={className}><EmptyState message="No market data" /></Card>;
  }

  const activeStrategies = STRATEGY_ORDER.filter((s) =>
    data.assets.some((a) => a.strategies?.[s])
  );

  return (
    <Card 
      title="Vue d’ensemble des actions"
      subtitle="Univers suivi · signaux techniques et proximité des seuils"
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
            </tr>
          </thead>
          <tbody>
            {sortedAssets.map((a) => {
              const assetType = getAssetType(a.symbol);
              return (
                <tr
                  key={a.symbol}
                  className="border-b border-white/5 hover:bg-white/[0.04] transition-all duration-200 group"
                >
                  <td className="py-4 px-6">
                    <div className="flex items-center gap-3 cursor-pointer" onClick={() => onSymbolClick && onSymbolClick(a.symbol)}>
                      <AssetIcon symbol={a.symbol} size="sm" />
                      <div className="flex flex-col">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white group-hover:text-green-400 transition-colors">{a.symbol}</span>
                          <span className={`text-[7px] font-black px-1 rounded ${assetType.bg} ${assetType.text} border ${assetType.border} uppercase`}>
                            {assetType.label}
                          </span>
                        </div>
                        <div className="text-[10px] text-[--text-muted] truncate max-w-[120px]">{a.name || 'Daily OHLCV'}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-right tabular-nums font-medium text-[--text-secondary]">
                    {formatPrice(a.close)}
                  </td>
                  {activeStrategies.map((s) => {
                    const strat = a.strategies?.[s];
                    if (!strat || strat.signal == null) {
                      return <td key={s} className="py-4 px-4 text-center text-[--text-muted] opacity-30">--</td>;
                    }
                    const sig = SIGNAL_COLORS[strat.signal] || SIGNAL_COLORS.NO_SIGNAL;

                    return (
                      <td key={s} className="py-4 px-4">
                        <div className="flex flex-col items-center gap-1.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${sig.bg} ${sig.text}`}>
                            {strat.signal === 'NO_SIGNAL' ? '--' : strat.signal}
                          </span>
                          {strat.indicator_value != null && (
                            <span className="text-[10px] text-[--text-secondary] tabular-nums font-medium">
                              {Number(strat.indicator_value).toFixed(s === 'ibs' ? 2 : s === 'rsi2' ? 1 : 0)}
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
