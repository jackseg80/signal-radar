import React, { forwardRef } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPnl, formatPct, pnlColor, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import AnimatedNumber from '../ui/AnimatedNumber';
import ProgressRing from '../ui/ProgressRing';
import { Wallet, TrendingUp, BarChart3, PieChart, Activity } from 'lucide-react';

const StrategyBreakdown = forwardRef(({ style, className, onMouseDown, onMouseUp, onTouchEnd, ...props }, ref) => {
  const { refreshKey } = useRefresh();
  const { data: perfData, loading: perfLoading, error: perfError, refetch: refetchPerf } = useApi(() => api.performanceSummary(), [refreshKey]);
  const { data: openData, loading: openLoading } = useApi(() => api.openPositions(), [refreshKey]);

  if (perfLoading || openLoading) return (
    <div ref={ref} style={style} className={`grid grid-cols-2 md:grid-cols-5 gap-4 ${className}`} {...props}>
      {[...Array(5)].map((_, i) => <Card key={i}><LoadingState rows={1} /></Card>)}
    </div>
  );
  
  if (perfError) return <Card ref={ref} style={style} className={className} {...props}><ErrorState message={perfError} onRetry={refetchPerf} /></Card>;
  if (!perfData || !perfData.paper) return null;

  // Map backend stats to the required format
  const stats = perfData.paper;
  const n_closed_trades = stats.n_trades || 0;
  const win_rate = stats.win_rate || 0;
  const total_realized_pnl = stats.total_pnl || 0;
  const n_open_positions = stats.n_open || 0;
  const by_strategy = stats.by_strategy || {};
  
  const initialCapital = 10000;
  const capital = initialCapital + total_realized_pnl;
  const total_unrealized_pnl = openData?.total_unrealized_pnl || 0;

  const realizedPct = initialCapital > 0 ? (total_realized_pnl / initialCapital * 100) : 0;
  const unrealizedPct = capital > 0 ? (total_unrealized_pnl / capital * 100) : 0;

  const kpis = [
    {
      label: 'Portfolio Equity',
      icon: <Wallet size={14} />,
      value: `$${capital.toLocaleString()}`,
      sub: `Initial: $${initialCapital.toLocaleString()}`,
      color: 'text-white',
    },
    {
      label: 'Realized PnL',
      icon: <TrendingUp size={14} />,
      animated: true,
      rawValue: total_realized_pnl,
      sub: formatPct(realizedPct),
      color: pnlColor(total_realized_pnl),
      glow: total_realized_pnl > 0 ? 'glow-green' : total_realized_pnl < 0 ? 'glow-red' : '',
    },
    {
      label: 'Unrealized PnL',
      icon: <Activity size={14} />,
      animated: true,
      rawValue: total_unrealized_pnl,
      sub: formatPct(unrealizedPct),
      color: pnlColor(total_unrealized_pnl),
      glow: total_unrealized_pnl > 0 ? 'glow-green' : total_unrealized_pnl < 0 ? 'glow-red' : '',
    },
    {
      label: 'Success Rate',
      icon: <PieChart size={14} />,
      isRing: n_closed_trades > 0,
      ringValue: win_rate,
      value: '--',
      color: 'text-[--text-muted]',
    },
    {
      label: 'Market Exposure',
      icon: <BarChart3 size={14} />,
      value: `${n_open_positions}`,
      sub: `Across ${Object.keys(by_strategy || {}).length} strategies`,
      color: 'text-white',
    },
  ];

  return (
    <div 
      ref={ref} 
      style={style} 
      className={`space-y-6 ${className}`}
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}
      onTouchEnd={onTouchEnd}
      {...props}
    >
      {/* KPI Row - Header is draggable area */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 cursor-grab active:cursor-grabbing">
        {kpis.map((kpi, idx) => (
          <div
            key={kpi.label}
            className={`bg-[--bg-card]/40 border border-[--glass-border] rounded-xl p-4 animate-slide-up transition-all hover:bg-[--bg-card]/60 hover:border-white/10 ${kpi.glow}`}
            style={{ animationDelay: `${idx * 50}ms` }}
          >
            <div className="flex items-center gap-2 mb-3">
               <div className="p-1.5 rounded-lg bg-white/5 text-[--text-muted]">
                 {kpi.icon}
               </div>
               <span 
                className="text-[10px] font-bold uppercase tracking-wider text-[--text-muted]"
                style={{ fontFamily: "'Space Grotesk', sans-serif" }}
               >
                 {kpi.label}
               </span>
            </div>

            {kpi.isRing ? (
              <div className="flex items-center gap-3">
                <ProgressRing
                  value={kpi.ringValue || 0}
                  size={48}
                  strokeWidth={4}
                  color={
                    kpi.ringValue >= 60 ? 'var(--accent-green)' :
                    kpi.ringValue >= 50 ? 'var(--accent-amber)' :
                    'var(--accent-red)'
                  }
                  label={kpi.ringValue != null ? `${kpi.ringValue.toFixed(0)}%` : '--'}
                />
                <div className="text-[10px] text-[--text-muted]">of {n_closed_trades} trades</div>
              </div>
            ) : kpi.animated ? (
              <div>
                <AnimatedNumber
                  value={kpi.rawValue}
                  format={formatPnl}
                  className={`text-xl font-bold tabular-nums ${kpi.color}`}
                />
                {kpi.sub && (
                  <div className={kpi.rawValue >= 0 ? 'text-green-500/80 text-[10px] mt-0.5' : 'text-red-500/80 text-[10px] mt-0.5'}>
                    {kpi.sub} from start
                  </div>
                )}
              </div>
            ) : (
              <div>
                <div className={`text-xl font-bold tabular-nums ${kpi.color}`}>{kpi.value}</div>
                {kpi.sub && (
                  <div className="text-[10px] text-[--text-muted] mt-0.5">{kpi.sub}</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Strategy Performance Details */}
      {by_strategy && Object.keys(by_strategy).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(by_strategy).map(([strat, stats]) => {
            const colors = STRATEGY_COLORS[strat] || STRATEGY_COLORS.rsi2;
            const winRate = stats.trades > 0 ? (stats.wins / stats.trades * 100) : 0;
            return (
              <div
                key={strat}
                className={`group relative overflow-hidden bg-[--bg-card]/20 border border-[--glass-border] rounded-xl p-4 hover:border-white/10 transition-all animate-fade-in`}
              >
                {/* Visual Accent */}
                <div className={`absolute top-0 left-0 w-1 h-full ${colors.bg}`} />
                
                <div className="flex items-center justify-between mb-4 pl-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest ${colors.bg} ${colors.text}`}
                    style={{ fontFamily: "'Space Grotesk', sans-serif" }}
                  >
                    {STRATEGY_LABELS[strat] || strat}
                  </span>
                  <div className="text-[10px] font-bold text-white/80 tabular-nums">
                    {winRate.toFixed(0)}% WR
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pl-2">
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-[--text-muted] mb-1">Net Profit</div>
                    <AnimatedNumber
                      value={stats.pnl}
                      format={formatPnl}
                      className={`text-sm font-bold ${pnlColor(stats.pnl)}`}
                    />
                  </div>
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-[--text-muted] mb-1">Volume</div>
                    <div className="text-sm font-bold text-white/90">
                      {stats.trades} <span className="text-[10px] text-[--text-muted] font-normal">Trades</span>
                    </div>
                  </div>
                </div>
                
                {/* Small progress bar for win rate */}
                <div className="mt-4 h-1 w-full bg-white/5 rounded-full overflow-hidden pl-2 ml-2">
                   <div 
                    className={`h-full transition-all duration-1000 ${winRate >= 50 ? 'bg-green-500/50' : 'bg-red-500/50'}`}
                    style={{ width: `${winRate}%` }} 
                   />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

StrategyBreakdown.displayName = "StrategyBreakdown";

export default StrategyBreakdown;
