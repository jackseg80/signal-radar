import React, { useState, useEffect, useMemo } from 'react';
import { 
  X, 
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
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import AssetIcon from '../ui/AssetIcon';

const MARKET_EVENTS = [
  { date: "2020-03-16", label: "COVID", color: "#ef4444" },
  { date: "2022-01-04", label: "Rate Hikes", color: "#f97316" },
  { date: "2018-12-24", label: "Dec 2018", color: "#eab308" },
  { date: "2016-11-08", label: "Election 2016", color: "#8b5cf6" },
];

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
    document.body.style.overflow = 'hidden';
    
    // Stabilisation pour Recharts après animation du modal
    const timer = setTimeout(() => setIsReady(true), 600);
    
    return () => {
      document.body.style.overflow = 'unset';
      clearTimeout(timer);
    };
  }, [symbol, strategy]);

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

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
    <div 
      className="fixed inset-0 z-[150] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in"
      onClick={handleBackdropClick}
    >
      <div className="bg-[#0f111a] border border-white/10 w-full max-w-6xl max-h-[90vh] rounded-3xl overflow-hidden shadow-2xl flex flex-col animate-slide-up relative">
        
        {/* Header Section */}
        <div className="relative p-6 sm:p-8 bg-gradient-to-b from-white/[0.03] to-transparent border-b border-white/5 shrink-0">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
            <div className="flex items-center gap-5">
              <AssetIcon symbol={symbol} size="lg" className="shadow-2xl ring-4 ring-white/5" />
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h2 className="text-3xl font-black text-white tracking-tight">{symbol}</h2>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border ${assetType.bg} ${assetType.text} ${assetType.border}`}>
                    {assetType.label}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 mt-3">
                  {availableStrategies.map((s) => (
                    <button
                      key={s}
                      onClick={() => {
                        setIsReady(false);
                        setStrategy(s);
                      }}
                      className={`px-4 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all cursor-pointer border ${
                        strategy === s 
                          ? 'bg-green-500 border-green-500 text-white shadow-[0_0_15px_rgba(34,197,94,0.3)]' 
                          : 'bg-white/5 border-white/5 text-[--text-muted] hover:text-white hover:bg-white/10'
                      }`}
                    >
                      {STRATEGY_LABELS[s] || s.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-8">
              <div className="text-right hidden sm:block">
                <p className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mb-1">Trades (OOS)</p>
                <p className="text-2xl font-mono font-bold text-white tabular-nums">
                  {data?.n_trades ?? '--'}
                </p>
              </div>
              <button 
                onClick={onClose}
                className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl text-white transition-all cursor-pointer border border-white/5"
              >
                <X size={24} />
              </button>
            </div>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 sm:p-8 custom-scrollbar">
          {loading ? (
            <LoadingState rows={10} />
          ) : error ? (
            <div className="space-y-6">
              <ErrorState message={error} />
              <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-3xl">
                <p className="text-sm text-red-400">
                  L'actif <strong>{symbol}</strong> n'est peut-être pas configuré pour la stratégie <strong>{strategy}</strong>.
                </p>
              </div>
            </div>
          ) : data && data.stats ? (
            <div className="space-y-10">
              
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatBox label="Max Drawdown" value={`${data.stats.max_drawdown_pct}%`} sub={data.stats.max_drawdown_date} color="text-red-400" icon={<ShieldAlert size={16} />} />
                <StatBox label="Meilleur Trade" value={`${data.stats.best_trade_pct}%`} color="text-green-400" icon={<TrendingUp size={16} />} />
                <StatBox label="Pire Trade" value={`${data.stats.worst_trade_pct}%`} color="text-red-400" icon={<TrendingDown size={16} />} />
                <StatBox label="Durée Moyenne" value={`${data.stats.avg_holding_days}j`} color="text-blue-400" icon={<Clock size={16} />} />
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                    <Activity size={14} className="text-blue-400" /> Performance Cumulative (OOS)
                  </h3>
                  <div className="text-xl font-mono font-bold text-white tabular-nums">
                    {data.equity_curve ? formatPrice(data.equity_curve[data.equity_curve.length - 1]?.equity) : '--'}
                  </div>
                </div>
                <div className="h-[350px] min-h-[350px] w-full bg-white/[0.02] rounded-[2rem] border border-white/5 p-6 overflow-hidden relative flex flex-col">
                  {isReady && data.equity_curve ? (
                    <ResponsiveContainer width="99%" height="99%">
                      <AreaChart data={data.equity_curve} syncId="asset-panel">
                        <defs>
                          <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                        <XAxis dataKey="date" hide />
                        <YAxis tick={{fill: '#64748b', fontSize: 10}} axisLine={false} tickLine={false} domain={['auto', 'auto']} orientation="right" />
                        <Tooltip content={<CustomTooltip />} />
                        <Area type="monotone" dataKey="equity" stroke="#3b82f6" strokeWidth={2} fill="url(#colorEquity)" isAnimationActive={false} />
                        {filteredMarketEvents.map((event, i) => (
                          <ReferenceLine key={i} x={event.date} stroke={event.color} strokeDasharray="3 3" label={{value: event.label, fill: event.color, fontSize: 8}} />
                        ))}
                        {data.trades?.map((t, i) => (
                          <ReferenceDot key={i} x={t.exit_date} y={equityCurveMap[t.exit_date] || data.equity_curve[0].equity} r={3} fill={t.is_winner ? "#22c55e" : "#ef4444"} stroke="none" isAnimationActive={false} />
                        ))}
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex-1 flex items-center justify-center"><LoadingState rows={3} /></div>
                  )}
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                  <ShieldAlert size={14} className="text-red-400" /> Drawdown Historique
                </h3>
                <div className="h-[120px] min-h-[120px] w-full bg-white/[0.01] rounded-2xl border border-white/5 p-4 overflow-hidden relative flex flex-col">
                  {isReady && data.equity_curve ? (
                    <ResponsiveContainer width="99%" height="99%">
                      <AreaChart data={data.equity_curve} syncId="asset-panel">
                        <XAxis dataKey="date" hide />
                        <YAxis hide domain={['auto', 0]} />
                        <Tooltip content={<CustomTooltip />} />
                        <Area type="monotone" dataKey="drawdown_pct" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} isAnimationActive={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex-1 flex items-center justify-center bg-white/5 animate-pulse rounded-xl" />
                  )}
                </div>
              </div>

            </div>
          ) : (
            <div className="p-20 text-center"><LoadingState rows={5} /></div>
          )}
        </div>
        
        <div className="p-6 bg-white/[0.02] border-t border-white/5 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-2 text-[10px] text-[--text-muted] uppercase font-bold tracking-widest">
            <Calendar size={12} /> Dernière mise à jour : {new Date().toLocaleDateString()}
          </div>
          <div className="text-[10px] text-blue-400 font-bold uppercase tracking-widest flex items-center gap-2">
            <Info size={12} /> Analyse Quantitative Out-of-Sample
          </div>
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, sub, icon, color }) {
  return (
    <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl hover:bg-white/[0.05] transition-all group">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-2 bg-white/5 rounded-lg text-[--text-muted]">{icon}</div>
        <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">{label}</span>
      </div>
      <div className="flex flex-col">
        <span className={`text-2xl font-black tracking-tight ${color}`}>{value}</span>
        {sub && <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mt-1 opacity-60">{sub}</span>}
      </div>
    </div>
  );
}
