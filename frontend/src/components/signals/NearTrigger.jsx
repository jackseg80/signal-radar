import React, { forwardRef } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import { Bell } from 'lucide-react';

/**
 * Extract near-trigger alerts from market overview data.
 */
function extractAlerts(assets) {
  const alerts = [];
  if (!assets) return alerts;

  for (const asset of assets) {
    for (const [strat, info] of Object.entries(asset.strategies || {})) {
      if (info.proximity?.near) {
        alerts.push({
          symbol: asset.symbol,
          strategy: strat,
          close: asset.close,
          proximity: info.proximity,
        });
      }
    }
  }

  // Sort by proximity pct descending (closest to trigger first)
  alerts.sort((a, b) => b.proximity.pct - a.proximity.pct);
  return alerts;
}

function AlertRow({ alert }) {
  const sc = STRATEGY_COLORS[alert.strategy] || STRATEGY_COLORS.rsi2;
  const pct = alert.proximity.pct;
  const barColor = pct >= 75
    ? 'var(--accent-green)'
    : pct >= 50
      ? 'var(--accent-amber)'
      : 'var(--text-muted)';
  const trendBlocked = alert.proximity.trend_ok === false;

  return (
    <div className={`group flex flex-col gap-2 p-3 rounded-lg border border-white/5 bg-white/[0.01] hover:bg-white/[0.03] transition-all ${
      trendBlocked ? 'opacity-50' : ''
    }`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm text-white">{alert.symbol}</span>
          <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${sc.bg} ${sc.text}`}>
            {STRATEGY_LABELS[alert.strategy] || alert.strategy}
          </span>
        </div>
        <span className="text-[10px] text-[--text-muted] tabular-nums">{formatPrice(alert.close)}</span>
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-[9px] text-[--text-muted]">
          <span>{alert.proximity.label}</span>
          <span className="tabular-nums font-medium text-[--text-secondary]">{pct.toFixed(0)}%</span>
        </div>
        <div className="w-full h-1 rounded-full bg-white/5 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000 ease-out"
            style={{ width: `${pct}%`, backgroundColor: barColor }}
          />
        </div>
      </div>

      {trendBlocked && (
        <div className="flex items-center gap-1.5 text-[9px] text-red-400/80 mt-1">
          <div className="w-1 h-1 rounded-full bg-red-400 animate-pulse" />
          Trend filter blocked (below SMA)
        </div>
      )}
    </div>
  );
}

const NearTrigger = forwardRef(({ style, className, onMouseDown, onMouseUp, onTouchEnd, ...props }, ref) => {
  const { refreshKey } = useRefresh();
  const { data, loading } = useApi(() => api.marketOverview(), [refreshKey]);

  if (loading) return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Approaching" icon={<Bell size={14} />}
      {...props}
    >
      <div className="animate-pulse space-y-3">
        <div className="h-16 bg-white/5 rounded-lg" />
        <div className="h-16 bg-white/5 rounded-lg" />
      </div>
    </Card>
  );

  const alerts = extractAlerts(data?.assets);
  
  return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Approaching" 
      subtitle={`${alerts.length} assets near trigger`}
      headerAction={<Bell size={14} className={alerts.length > 0 ? "text-amber-400 animate-bounce" : "text-[--text-muted]"} />}
      {...props}
    >
      {alerts.length === 0 ? (
        <div className="py-8 text-center text-xs text-[--text-muted] italic bg-white/[0.01] rounded-lg border border-dashed border-white/5">
          No assets near trigger
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => (
            <AlertRow key={`${a.symbol}-${a.strategy}`} alert={a} />
          ))}
        </div>
      )}
    </Card>
  );
});

NearTrigger.displayName = "NearTrigger";

export default NearTrigger;
