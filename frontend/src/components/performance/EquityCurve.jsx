import React, { forwardRef } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid } from 'recharts';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPnl, formatDate } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';

const EquityCurve = forwardRef(({ style, className, onMouseDown, onMouseUp, onTouchEnd, ...props }, ref) => {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.equityCurve(), [refreshKey]);

  if (loading) return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Equity Curve"
      {...props}
    >
      <LoadingState rows={4} />
    </Card>
  );
  
  if (error) return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Equity Curve"
      {...props}
    >
      <ErrorState message={error} onRetry={refetch} />
    </Card>
  );

  const points = data?.data_points || [];

  if (points.length < 2) {
    return (
      <Card 
        ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
        title="Equity Curve"
        {...props}
      >
        <EmptyState message="Not enough trades yet for equity curve" />
      </Card>
    );
  }

  return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Equity Curve"
      {...props}
    >
      <ResponsiveContainer width="100%" height="100%" minHeight={200}>
        <AreaChart data={points} margin={{ top: 5, right: 5, bottom: 5, left: 5 }} style={{ cursor: 'crosshair' }}>
          <defs>
            <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-green)" stopOpacity={0.25} />
              <stop offset="100%" stopColor="var(--accent-green)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="var(--text-muted)"
            fontSize={10}
            tickLine={false}
            axisLine={false}
            minTickGap={30}
          />
          <YAxis
            stroke="var(--text-muted)"
            fontSize={10}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${v / 1000}k`}
          />
          <Tooltip
            contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '8px', fontSize: '12px' }}
            itemStyle={{ color: 'var(--accent-green)' }}
            formatter={(value) => [formatPnl(value), 'Equity']}
            labelFormatter={formatDate}
          />
          <ReferenceLine y={10000} stroke="rgba(255,255,255,0.1)" strokeDasharray="3 3" />
          <Area
            type="monotone"
            dataKey="equity"
            stroke="var(--accent-green)"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#pnlGradient)"
            dot={false}
            activeDot={{ r: 5, fill: 'var(--accent-green)', stroke: 'rgba(34, 197, 94, 0.3)', strokeWidth: 6 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
});

EquityCurve.displayName = "EquityCurve";

export default EquityCurve;
