import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';

/**
 * Extract near-trigger alerts from market overview data.
 * Returns sorted array of { symbol, strategy, close, proximity }.
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

function AlertCard({ alert }) {
  const sc = STRATEGY_COLORS[alert.strategy] || STRATEGY_COLORS.rsi2;
  const pct = alert.proximity.pct;
  const barColor = pct >= 75
    ? 'var(--accent-green)'
    : pct >= 50
      ? 'var(--accent-amber)'
      : 'var(--text-muted)';
  const trendBlocked = alert.proximity.trend_ok === false;

  return (
    <div className={`flex-shrink-0 w-52 rounded-lg border border-[--border-subtle] p-3 ${
      trendBlocked ? 'opacity-50' : ''
    }`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-sm">{alert.symbol}</span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${sc.bg} ${sc.text}`}>
          {STRATEGY_LABELS[alert.strategy] || alert.strategy}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 rounded-full bg-white/5 overflow-hidden mb-2">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: barColor }}
        />
      </div>

      <div className="flex items-center justify-between text-[10px]">
        <span className="text-[--text-muted] tabular-nums">{alert.proximity.label}</span>
        <div className="flex items-center gap-1">
          {alert.proximity.trend_ok !== null && (
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                alert.proximity.trend_ok ? 'bg-green-400' : 'bg-red-400'
              }`}
              title={alert.proximity.trend_ok ? 'Trend OK' : 'Trend blocked'}
            />
          )}
          <span className="text-[--text-secondary] tabular-nums">{formatPrice(alert.close)}</span>
        </div>
      </div>

      {trendBlocked && (
        <div className="text-[9px] text-red-400/70 mt-1">Trend blocked</div>
      )}
    </div>
  );
}

export default function NearTrigger() {
  const { refreshKey } = useRefresh();
  const { data, loading } = useApi(() => api.marketOverview(), [refreshKey]);

  if (loading) return null;

  const alerts = extractAlerts(data?.assets);
  if (alerts.length === 0) return null;

  return (
    <Card title="Approaching Trigger">
      <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
        {alerts.map((a) => (
          <AlertCard key={`${a.symbol}-${a.strategy}`} alert={a} />
        ))}
      </div>
    </Card>
  );
}
