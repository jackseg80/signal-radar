import React, { useState, forwardRef } from 'react';
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid, Legend } from 'recharts';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPnl, formatDate } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';

const buildLiveCurve = (closedTrades, initialCapital = 1000) => {
  const sorted = [...closedTrades].sort((a, b) => 
    new Date(a.exit_date) - new Date(b.exit_date)
  );
  let equity = initialCapital;
  return [
    { date: sorted[0]?.entry_date || new Date().toISOString(), equity },
    ...sorted.map(t => {
      equity += (t.pnl_dollars || 0);
      return { date: t.exit_date, equity: Math.round(equity * 100) / 100 };
    })
  ];
};

const EquityCurve = forwardRef(({ style, className, onMouseDown, onMouseUp, onTouchEnd, ...props }, ref) => {
  const [mode, setMode] = useState('paper'); // 'paper' | 'live' | 'both'
  const { refreshKey } = useRefresh();
  
  // Fetch multiple endpoints
  const { data, loading, error, refetch } = useApi(async () => {
    const [paperData, liveData, settings] = await Promise.all([
      api.equityCurve(),
      api.liveClosed(),
      api.getSettings()
    ]);
    return { paperData, liveData, settings };
  }, [refreshKey]);

  const titleNode = (
    <div className="flex items-center justify-between w-full pr-4">
      <span>Equity Curve</span>
      <div className="flex rounded-lg overflow-hidden border border-[--border-subtle] text-xs">
        {['paper', 'live', 'both'].map(m => (
          <button
            key={m}
            onMouseDown={(e) => e.stopPropagation()} // Prevent drag when clicking toggle
            onClick={(e) => { e.stopPropagation(); setMode(m); }}
            className={`px-3 py-1 capitalize transition-colors ${
              mode === m 
                ? 'bg-white/10 text-white' 
                : 'text-[--text-muted] hover:text-[--text-primary] bg-transparent'
            }`}
          >
            {m}
          </button>
        ))}
      </div>
    </div>
  );

  if (loading) return (
    <Card ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd} title={titleNode} {...props}>
      <LoadingState rows={4} />
    </Card>
  );
  
  if (error) return (
    <Card ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd} title={titleNode} {...props}>
      <ErrorState message={error} onRetry={refetch} />
    </Card>
  );

  const paperPoints = data?.paperData?.data_points || [];
  const liveTrades = data?.liveData?.trades || [];
  
  const liveInitial = data?.settings?.initial_capital || 1000;
  const paperInitial = data?.settings?.initial_capital || 5000;

  const livePoints = liveTrades.length > 0 ? buildLiveCurve(liveTrades, liveInitial) : [];

  // Determine which data to show
  let displayPoints = [];
  let isEmpty = false;
  let emptyMessage = "";

  if (mode === 'paper') {
    displayPoints = paperPoints;
    isEmpty = paperPoints.length < 2;
    emptyMessage = "Not enough paper trades yet for equity curve";
  } else if (mode === 'live') {
    displayPoints = livePoints;
    isEmpty = livePoints.length < 2;
    emptyMessage = "No closed live trades yet";
  } else {
    // Both mode: we need to merge data points by date for Recharts
    isEmpty = paperPoints.length < 2 && livePoints.length < 2;
    emptyMessage = "Not enough trades to build curves";
    
    if (!isEmpty) {
      const dateMap = new Map();
      
      // Seed with all dates
      paperPoints.forEach(p => dateMap.set(p.date, { date: p.date, paperEquity: p.equity }));
      livePoints.forEach(p => {
        if (dateMap.has(p.date)) {
          dateMap.get(p.date).liveEquity = p.equity;
        } else {
          dateMap.set(p.date, { date: p.date, liveEquity: p.equity });
        }
      });
      
      displayPoints = Array.from(dateMap.values()).sort((a, b) => new Date(a.date) - new Date(b.date));
      
      // Forward-fill missing values so lines don't break
      let lastPaper = paperInitial;
      let lastLive = liveInitial;
      
      displayPoints.forEach(p => {
        if (p.paperEquity === undefined) p.paperEquity = lastPaper;
        else lastPaper = p.paperEquity;
        
        if (p.liveEquity === undefined) p.liveEquity = lastLive;
        else lastLive = p.liveEquity;
      });
    }
  }

  if (isEmpty) {
    return (
      <Card ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd} title={titleNode} {...props}>
        <EmptyState message={emptyMessage} />
      </Card>
    );
  }

  const yAxisFormatter = (v) => `$${v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v}`;

  return (
    <Card ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd} title={titleNode} {...props}>
      <ResponsiveContainer width="100%" height="100%" minHeight={200}>
        {mode === 'both' ? (
          <LineChart data={displayPoints} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={formatDate} stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} minTickGap={30} />
            <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} tickFormatter={yAxisFormatter} />
            <Tooltip
              contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '8px', fontSize: '12px' }}
              labelFormatter={formatDate}
              formatter={(value, name) => [formatPnl(value), name === 'paperEquity' ? 'Paper' : 'Live']}
            />
            <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px', color: 'var(--text-muted)' }}/>
            <Line type="stepAfter" dataKey="paperEquity" name="Paper Trading" stroke="var(--accent-blue, #3b82f6)" strokeWidth={2} dot={false} />
            <Line type="stepAfter" dataKey="liveEquity" name="Live Trading" stroke="var(--accent-green)" strokeWidth={2} dot={false} />
          </LineChart>
        ) : (
          <AreaChart data={displayPoints} margin={{ top: 5, right: 5, bottom: 5, left: 5 }} style={{ cursor: 'crosshair' }}>
            <defs>
              <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={mode === 'live' ? 'var(--accent-green)' : 'var(--accent-blue, #3b82f6)'} stopOpacity={0.25} />
                <stop offset="100%" stopColor={mode === 'live' ? 'var(--accent-green)' : 'var(--accent-blue, #3b82f6)'} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={formatDate} stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} minTickGap={30} />
            <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} tickFormatter={yAxisFormatter} />
            <Tooltip
              contentStyle={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '8px', fontSize: '12px' }}
              itemStyle={{ color: mode === 'live' ? 'var(--accent-green)' : 'var(--accent-blue, #3b82f6)' }}
              formatter={(value) => [formatPnl(value), 'Equity']}
              labelFormatter={formatDate}
            />
            <ReferenceLine y={mode === 'live' ? liveInitial : paperInitial} stroke="rgba(255,255,255,0.1)" strokeDasharray="3 3" />
            <Area
              type="stepAfter"
              dataKey="equity"
              stroke={mode === 'live' ? 'var(--accent-green)' : 'var(--accent-blue, #3b82f6)'}
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#pnlGradient)"
              dot={false}
              activeDot={{ r: 5, fill: mode === 'live' ? 'var(--accent-green)' : 'var(--accent-blue, #3b82f6)', stroke: 'rgba(255,255,255,0.3)', strokeWidth: 6 }}
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </Card>
  );
});

EquityCurve.displayName = "EquityCurve";

export default EquityCurve;
