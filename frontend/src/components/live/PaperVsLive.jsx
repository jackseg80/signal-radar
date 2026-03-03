import React, { forwardRef } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPnl, pnlColor } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';

function StatCard({ label, data }) {
  if (!data) return null;
  return (
    <div className="bg-[--bg-primary] rounded-lg p-4 flex-1 min-w-[180px]">
      <div className="text-xs font-semibold uppercase tracking-wider text-[--text-muted] mb-3">{label}</div>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-[--text-muted]">Trades</span>
          <span className="text-[--text-primary] font-medium">{data.n_trades}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[--text-muted]">Win Rate</span>
          <span className="text-[--text-primary]">{data.win_rate.toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[--text-muted]">Total PnL</span>
          <span className={`font-medium ${pnlColor(data.total_pnl)}`}>{formatPnl(data.total_pnl)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[--text-muted]">Avg/Trade</span>
          <span className={pnlColor(data.avg_pnl_per_trade)}>{formatPnl(data.avg_pnl_per_trade)}</span>
        </div>
      </div>
    </div>
  );
}

const PaperVsLive = forwardRef(({ style, className, onMouseDown, onMouseUp, onTouchEnd, ...props }, ref) => {
  const { refreshKey } = useRefresh();
  const { data, loading } = useApi(() => api.liveCompare(), [refreshKey]);

  if (loading) return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Paper vs Live"
      {...props}
    >
      <LoadingState />
    </Card>
  );
  
  if (!data) return null;

  const hasPaper = data.paper?.n_trades > 0;
  const hasLive = data.live?.n_trades > 0;

  if (!hasPaper && !hasLive) return null;

  return (
    <Card 
      ref={ref} style={style} className={className} onMouseDown={onMouseDown} onMouseUp={onMouseUp} onTouchEnd={onTouchEnd}
      title="Paper vs Live"
      {...props}
    >
      <div className="flex gap-4 flex-wrap">
        <StatCard label="Paper" data={data.paper} />
        <StatCard label="Live" data={data.live} />
      </div>
    </Card>
  );
});

PaperVsLive.displayName = "PaperVsLive";

export default PaperVsLive;
