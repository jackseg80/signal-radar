import React from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, SIGNAL_COLORS, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import { Table } from 'lucide-react';

const STRATEGY_ORDER = ['rsi2', 'ibs', 'tom'];

function ProximityBar({ proximity }) {
  if (!proximity || proximity.pct == null) return null;

  const pct = proximity.pct;
  const barColor = pct >= 75
    ? 'var(--accent-green)'
    : pct >= 50
      ? 'var(--accent-amber)'
      : 'var(--text-muted)';

  const trendBlocked = proximity.trend_ok === false;

  return (
    <div className={`mt-1 flex items-center gap-2 justify-center ${trendBlocked ? 'opacity-40' : ''}`}>
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

export default function MarketOverview({ className }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.marketOverview(), [refreshKey]);

  if (loading) return <Card title="Market Overview" className={className}><LoadingState rows={8} /></Card>;
  if (error) return <Card title="Market Overview" className={className}><ErrorState message={error} onRetry={refetch} /></Card>;

  const assets = data?.assets || [];
  if (assets.length === 0) {
    return <Card title="Market Overview" className={className}><EmptyState message="No market data" /></Card>;
  }

  const activeStrategies = STRATEGY_ORDER.filter((s) =>
    assets.some((a) => a.strategies[s])
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
              <th className="text-left py-4 px-6">Asset</th>
              <th className="text-right py-4 px-4">Price</th>
              {activeStrategies.map((s) => {
                const sc = STRATEGY_COLORS[s] || STRATEGY_COLORS.rsi2;
                return (
                  <th key={s} className="text-center py-4 px-4">
                    <div className="flex flex-col items-center">
                      <span className={`${sc.text}`}>{STRATEGY_LABELS[s] || s}</span>
                    </div>
                  </th>
                );
              })}
              <th className="text-center py-4 px-6">Positions</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr
                key={a.symbol}
                className={`border-b border-white/5 hover:bg-white/[0.04] transition-all duration-200 group ${
                  a.has_open_position ? 'bg-green-500/[0.03]' : ''
                }`}
              >
                <td className="py-4 px-6">
                  <div className="flex flex-col">
                    <span className="font-bold text-white group-hover:text-green-400 transition-colors">{a.symbol}</span>
                    <span className="text-[10px] text-[--text-muted]">Daily OHLCV</span>
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
                  if (s === 'rsi2' && strat.indicator_value != null) {
                    barPct = Math.max(0, Math.min(100, (1 - strat.indicator_value / 30) * 100));
                    barColor = strat.indicator_value < 10 ? 'var(--accent-green)' : strat.indicator_value < 20 ? 'var(--accent-amber)' : 'var(--text-muted)';
                  } else if (s === 'ibs' && strat.indicator_value != null) {
                    barPct = Math.max(0, Math.min(100, (1 - strat.indicator_value / 0.5) * 100));
                    barColor = strat.indicator_value < 0.2 ? 'var(--accent-green)' : strat.indicator_value < 0.35 ? 'var(--accent-amber)' : 'var(--text-muted)';
                  }

                  return (
                    <td key={s} className="py-4 px-4">
                      <div className="flex flex-col items-center gap-1.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${sig.bg} ${sig.text}`}>
                          {strat.signal === 'NO_SIGNAL' ? '--' : strat.signal}
                        </span>
                        
                        {strat.indicator_value != null && (
                          <div className="flex flex-col items-center">
                            <span className="text-[10px] text-[--text-secondary] tabular-nums font-medium">
                              {Number(strat.indicator_value).toFixed(s === 'ibs' ? 2 : s === 'rsi2' ? 1 : 0)}
                            </span>
                            {(s === 'rsi2' || s === 'ibs') && (
                              <div className="w-10 h-1 rounded-full bg-white/5 overflow-hidden mt-0.5">
                                <div
                                  className="h-full rounded-full transition-all duration-700"
                                  style={{ width: `${barPct}%`, backgroundColor: barColor }}
                                />
                              </div>
                            )}
                          </div>
                        )}
                        {strat.proximity?.near && <ProximityBar proximity={strat.proximity} />}
                      </div>
                    </td>
                  );
                })}
                <td className="py-4 px-6 text-center">
                  {a.has_open_position ? (
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-green-400 text-[10px] font-bold uppercase tracking-widest bg-green-500/10 px-2 py-0.5 rounded-full border border-green-500/20">
                        OPEN
                      </span>
                      <div className="flex gap-1 justify-center">
                        {a.position_strategies.map((s) => {
                          const sc = STRATEGY_COLORS[s] || STRATEGY_COLORS.rsi2;
                          return (
                            <span key={s} className={`text-[8px] uppercase font-bold ${sc.text}`}>
                              {STRATEGY_LABELS[s] || s}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  ) : (
                    <span className="text-[--text-muted] opacity-20">--</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
