import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPnl } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-[--bg-card] border border-[--border-subtle] rounded-lg p-3 text-xs shadow-xl">
      <div className="text-[--text-secondary] mb-1">{d.date}</div>
      <div className="font-medium">Cumulative: {formatPnl(d.cumulative_pnl)}</div>
      <div className="text-[--text-muted]">
        Trade: {formatPnl(d.trade_pnl)} ({d.strategy} {d.symbol})
      </div>
    </div>
  );
}

export default function EquityCurve() {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.equityCurve(), [refreshKey]);

  if (loading) return <Card title="Equity Curve"><LoadingState rows={4} /></Card>;
  if (error) return <Card title="Equity Curve"><ErrorState message={error} onRetry={refetch} /></Card>;

  const points = data?.data_points || [];

  if (points.length < 2) {
    return (
      <Card title="Equity Curve">
        <EmptyState message="Not enough trades yet for equity curve" />
      </Card>
    );
  }

  return (
    <Card title="Equity Curve">
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={points} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <defs>
            <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-green)" stopOpacity={0.2} />
              <stop offset="100%" stopColor="var(--accent-green)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            axisLine={{ stroke: 'var(--border-subtle)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${v}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke="var(--border-subtle)" strokeDasharray="3 3" />
          <Area
            type="monotone"
            dataKey="cumulative_pnl"
            stroke="var(--accent-green)"
            strokeWidth={2}
            fill="url(#pnlGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}
