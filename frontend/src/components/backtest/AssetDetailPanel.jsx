import React, { useState, useEffect, useMemo } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  Clock, 
  Activity, 
  Target, 
  ShieldAlert,
  Info
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  ReferenceLine,
  ReferenceDot
} from 'recharts';
import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';
import { 
  formatPrice, 
  formatPct, 
  formatPnl, 
  formatDate, 
  getAssetType,
  STRATEGY_LABELS
} from '../../utils/format';
import { MARKET_EVENTS } from '../../constants/market';
import BaseModal from '../ui/BaseModal';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import AssetIcon from '../ui/AssetIcon';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="bg-[#1a1d27] border border-white/10 p-3 rounded-lg shadow-xl backdrop-blur-md">
        <p className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mb-1">{formatDate(label)}</p>
        <div className="space-y-1">
          <p className="text-sm font-bold text-white">Equity: {formatPrice(d.equity)}</p>
          <p className={`text-xs font-medium ${d.drawdown_pct < 0 ? 'text-red-400' : 'text-green-400'}`}>
            Drawdown: {d.drawdown_pct?.toFixed(2)}%
          </p>
        </div>
      </div>
    );
  }
  return null;
};

export default function AssetDetailPanel({ symbol, initialStrategy, matrixData, onClose }) {
  const [strategy, setStrategy] = useState(initialStrategy);
  const [isReady, setIsReady] = useState(false);

  const { data, loading, error } = useApi(
    () => api.backtestEquityCurve(strategy, symbol),
    [symbol, strategy]
  );

  useEffect(() => {
    if (!symbol) return;
    // Safety delay for Recharts calculations
    const timer = setTimeout(() => setIsReady(true), 600);
    return () => clearTimeout(timer);
  }, [symbol, strategy]);

  const availableStrategies = useMemo(() => {
    if (!matrixData?.[symbol]) return [strategy];
    if (typeof matrixData[symbol] === 'object' && !Array.isArray(matrixData[symbol])) {
        return Object.keys(matrixData[symbol]);
    }
    return [strategy];
  }, [matrixData, symbol, strategy]);

  const assetType = getAssetType(symbol);

  const equityCurveMap = useMemo(() => {
    if (!data?.equity_curve) return {};
    return data.equity_curve.reduce((acc, curr) => {
      acc[curr.date] = curr.equity;
      return acc;
    }, {});
  }, [data]);

  const filteredMarketEvents = useMemo(() => {
    if (!data?.equity_curve || data.equity_curve.length === 0) return [];
    const startDate = data.equity_curve[0].date;
    const endDate = data.equity_curve[data.equity_curve.length - 1].date;
    return MARKET_EVENTS.filter(e => e.date >= startDate && e.date <= endDate);
  }, [data]);

  if (!symbol) return null;

  return (
    <BaseModal 
      onClose={onClose}
      title={symbol}
      subtitle="Analyse de Backtest OOS 2014-2025"
      icon={() => <AssetIcon symbol={symbol} size="lg" className="shadow-2xl" />}
    >
      <div className="p-8 lg:p-10 flex flex-col gap-10">
        {/* Strategy Switcher */}
        <div className="flex flex-wrap gap-2 p-1 bg-white/[0.02] border border-white/5 rounded-xl w-fit">
          {availableStrategies.map((s) => (
            <button
              key={s}
              onClick={() => {
                setIsReady(false);
                setStrategy(s);
              }}
              className={`px-4 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all cursor-pointer border ${
                strategy === s 
                  ? 'bg-green-500 border-green-500 text-white shadow-[0_0_15px_rgba(34,197,94,0.3)]' 
                  : 'bg-white/5 border-white/5 text-[--text-muted] hover:text-white hover:bg-white/10'
              }`}
            >
              {STRATEGY_LABELS[s] || s.toUpperCase()}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-10">
            <div className="grid grid-cols-4 gap-4">
              {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-white/[0.02] animate-pulse rounded-3xl" />)}
            </div>
            <div className="h-[350px] bg-white/[0.02] animate-pulse rounded-3xl" />
          </div>
        ) : error ? (
          <div className="space-y-6">
            <ErrorState message={error} />
            <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-3xl">
              <p className="text-sm text-red-400 text-center">
                L'actif <strong>{symbol}</strong> n'est peut-être pas configuré pour la stratégie <strong>{strategy}</strong>.
              </p>
            </div>
          </div>
        ) : data && data.stats ? (
          <div className="space-y-12">
            
            {/* Stats Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
              <StatBox label="Max Drawdown" value={`${data.stats.max_drawdown_pct}%`} sub={data.stats.max_drawdown_date} color="text-red-400" icon={<ShieldAlert size={16} />} />
              <StatBox label="Meilleur Trade" value={`${data.stats.best_trade_pct}%`} color="text-green-400" icon={<TrendingUp size={16} />} />
              <StatBox label="Pire Trade" value={`${data.stats.worst_trade_pct}%`} color="text-red-400" icon={<TrendingDown size={16} />} />
              <StatBox label="Durée Moyenne" value={`${data.stats.avg_holding_days}j`} color="text-blue-400" icon={<Clock size={16} />} />
            </div>

            {/* Equity Chart */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                  <Activity size={14} className="text-blue-400" /> Performance Cumulative (OOS)
                </h3>
                <div className="text-xl font-mono font-bold text-white tabular-nums">
                  {formatPrice(data.equity_curve[data.equity_curve.length - 1]?.equity)}
                  <span className={`ml-3 text-sm ${data.stats.max_drawdown_pct > -10 ? 'text-green-400' : 'text-amber-400'}`}>
                    {(((data.equity_curve[data.equity_curve.length - 1].equity - data.equity_curve[0].equity) / data.equity_curve[0].equity) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              <div className="h-[350px] min-h-[350px] w-full bg-white/[0.02] rounded-[2rem] border border-white/5 p-6 overflow-hidden relative flex flex-col shadow-inner">
                {isReady && data.equity_curve ? (
                  <ResponsiveContainer width="99%" height="99%">
                    <AreaChart data={data.equity_curve} syncId="asset-panel" margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                      <XAxis dataKey="date" hide />
                      <YAxis tick={{fill: '#64748b', fontSize: 10}} axisLine={false} tickLine={false} domain={['auto', 'auto']} orientation="right" tickFormatter={(val) => `$${(val / 1000).toFixed(1)}k`} />
                      <Tooltip content={<CustomTooltip />} />
                      <Area type="monotone" dataKey="equity" stroke="#3b82f6" strokeWidth={3} fill="url(#colorEquity)" isAnimationActive={false} />
                      {filteredMarketEvents.map((event, i) => (
                        <ReferenceLine key={i} x={event.date} stroke={event.color} strokeDasharray="3 3" label={{value: event.label, fill: event.color, fontSize: 8, position: 'insideTopLeft'}} />
                      ))}
                      {data.trades?.map((t, i) => (
                        <ReferenceDot key={i} x={t.exit_date} y={equityCurveMap[t.exit_date] || data.equity_curve[0].equity} r={3} fill={t.is_winner ? "#22c55e" : "#ef4444"} stroke="none" isAnimationActive={false} />
                      ))}
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex-1 flex items-center justify-center animate-pulse">
                    <div className="w-10 h-10 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                  </div>
                )}
              </div>
            </div>

            {/* Drawdown Chart */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                <ShieldAlert size={14} className="text-red-400" /> Profil de Risque (Drawdown)
              </h3>
              <div className="h-[120px] min-h-[120px] w-full bg-white/[0.01] rounded-2xl border border-white/5 p-4 overflow-hidden relative flex flex-col shadow-inner">
                {isReady && data.equity_curve ? (
                  <ResponsiveContainer width="99%" height="99%">
                    <AreaChart data={data.equity_curve} syncId="asset-panel">
                      <XAxis dataKey="date" hide />
                      <YAxis hide domain={['auto', 0]} />
                      <Tooltip content={<CustomTooltip />} />
                      <Area type="monotone" dataKey="drawdown_pct" stroke="#ef4444" strokeWidth={2} fill="#ef4444" fillOpacity={0.15} isAnimationActive={false} />
                      <ReferenceLine y={0} stroke="#ffffff10" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex-1 bg-white/5 animate-pulse rounded-xl" />
                )}
              </div>
            </div>

            {/* Footer Notice */}
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-3xl p-6 flex gap-5">
              <div className="w-12 h-12 rounded-2xl bg-blue-500/20 flex items-center justify-center shrink-0">
                <Info size={24} className="text-blue-400" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white mb-1 uppercase tracking-tight">Analyse Out-of-Sample</h4>
                <p className="text-xs text-blue-100/60 leading-relaxed">
                  Cette simulation utilise des données que l'algorithme n'a jamais "vues" lors de sa phase de conception. 
                  Elle représente la performance réelle attendue si la stratégie avait été lancée au 1er Janvier 2014.
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </BaseModal>
  );
}

function StatBox({ label, value, sub, icon, color }) {
  return (
    <div className="p-6 bg-white/[0.03] border border-white/5 rounded-3xl hover:bg-white/[0.05] transition-all group">
      <div className="flex items-center gap-3 mb-3 text-[--text-muted]">
        <div className="p-2 bg-white/5 rounded-lg group-hover:text-white transition-colors">{icon}</div>
        <span className="text-[10px] font-bold uppercase tracking-widest">{label}</span>
      </div>
      <div className="flex flex-col">
        <span className={`text-2xl font-black tracking-tight ${color}`}>{value}</span>
        {sub && <span className="text-[10px] font-bold text-[--text-muted] uppercase mt-1 opacity-60 tabular-nums">{sub}</span>}
      </div>
    </div>
  );
}
