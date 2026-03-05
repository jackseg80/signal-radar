import React, { useState, useEffect, useMemo } from 'react';
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
import { 
  X, 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  ShieldCheck, 
  Activity, 
  Target, 
  Info, 
  Clock, 
  ShieldAlert 
} from 'lucide-react';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import AssetIcon from '../ui/AssetIcon';
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

const MARKET_EVENTS = [
  { date: "2020-03-16", label: "COVID", color: "#ef4444" },
  { date: "2022-01-04", label: "Rate Hikes", color: "#f97316" },
  { date: "2018-12-24", label: "Dec 2018", color: "#eab308" },
  { date: "2016-11-08", label: "Election 2016", color: "#8b5cf6" },
];

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
    
    // Delay very long to be 100% sure modal is rendered before Recharts
    const timer = setTimeout(() => setIsReady(true), 1000);
    
    return () => {
      document.body.style.overflow = 'unset';
      clearTimeout(timer);
    };
  }, [symbol, strategy]);

  if (!symbol) return null;

  const assetType = getAssetType(symbol);

  const availableStrategies = useMemo(() => {
    if (!matrixData?.[symbol]) return [strategy];
    if (typeof matrixData[symbol] === 'object' && !Array.isArray(matrixData[symbol])) {
        return Object.keys(matrixData[symbol]);
    }
    return [strategy];
  }, [matrixData, symbol, strategy]);

  const equityCurveMap = useMemo(() => {
    if (!data?.equity_curve) return {};
    return data.equity_curve.reduce((acc, curr) => {
      acc[curr.date] = curr.equity;
      return acc;
    }, {});
  }, [data]);

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div 
      className="fixed inset-0 z-[150] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in"
      onClick={handleBackdropClick}
    >
      <div className="bg-[#0f111a] border border-white/10 w-full max-w-6xl max-h-[90vh] rounded-3xl overflow-hidden shadow-2xl flex flex-col animate-slide-up">
        
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
                  {data?.n_trades || '--'}
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
              <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-3xl text-sm text-red-400">
                L'actif <strong>{symbol}</strong> n'est peut-être pas configuré pour la stratégie <strong>{strategy}</strong>.
              </div>
            </div>
          ) : (
            <div className="space-y-10">
              
              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl">
                  <div className="flex items-center gap-2 mb-3 text-[--text-muted]">
                    <ShieldAlert size={16} />
                    <span className="text-[10px] font-bold uppercase tracking-widest">Max Drawdown</span>
                  </div>
                  <p className="text-2xl font-black text-red-400 tracking-tight">{data?.stats?.max_drawdown_pct}%</p>
                  {data?.stats?.max_drawdown_date && <p className="text-[10px] text-[--text-muted] mt-1 uppercase">{data.stats.max_drawdown_date}</p>}
                </div>
                <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl">
                  <div className="flex items-center gap-2 mb-3 text-[--text-muted]">
                    <TrendingUp size={16} />
                    <span className="text-[10px] font-bold uppercase tracking-widest">Meilleur Trade</span>
                  </div>
                  <p className="text-2xl font-black text-green-400 tracking-tight">+{data?.stats?.best_trade_pct}%</p>
                </div>
                <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl">
                  <div className="flex items-center gap-2 mb-3 text-[--text-muted]">
                    <TrendingDown size={16} />
                    <span className="text-[10px] font-bold uppercase tracking-widest">Pire Trade</span>
                  </div>
                  <p className="text-2xl font-black text-red-400 tracking-tight">{data?.stats?.worst_trade_pct}%</p>
                </div>
                <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl">
                  <div className="flex items-center gap-2 mb-3 text-[--text-muted]">
                    <Clock size={16} />
                    <span className="text-[10px] font-bold uppercase tracking-widest">Durée Moyenne</span>
                  </div>
                  <p className="text-2xl font-black text-blue-400 tracking-tight">{data?.stats?.avg_holding_days}j</p>
                </div>
              </div>

              {/* Chart Section */}
              <div className="space-y-4">
                <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                  <Activity size={14} className="text-blue-400" /> Performance Cumulative OOS (2014-2025)
                </h3>
                <div className="h-[400px] min-h-[400px] w-full bg-white/[0.02] rounded-3xl border border-white/5 p-6 flex flex-col">
                  {isReady && data?.equity_curve ? (
                    <div className="flex-1 w-full overflow-hidden">
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
                          <YAxis 
                            domain={['auto', 'auto']} 
                            orientation="right"
                            tick={{ fill: '#64748b', fontSize: 10 }}
                            axisLine={false}
                            tickLine={false}
                            tickFormatter={(val) => `$${(val / 1000).toFixed(1)}k`}
                          />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid #ffffff10', borderRadius: '12px' }}
                            itemStyle={{ color: '#fff', fontSize: '12px' }}
                          />
                          <Area 
                            type="monotone" 
                            dataKey="equity" 
                            stroke="#3b82f6" 
                            strokeWidth={3}
                            fillOpacity={1} 
                            fill="url(#colorEquity)" 
                            isAnimationActive={false}
                          />
                          {MARKET_EVENTS.map((event, i) => (
                            <ReferenceLine 
                              key={i} 
                              x={event.date} 
                              stroke={event.color} 
                              strokeDasharray="3 3" 
                              label={{ value: event.label, fill: event.color, fontSize: 8, position: 'insideTopLeft' }} 
                            />
                          ))}
                          {data.trades?.map((t, i) => (
                            <ReferenceDot 
                              key={i} 
                              x={t.exit_date} 
                              y={equityCurveMap[t.exit_date] || data.equity_curve[0].equity} 
                              r={3} 
                              fill={t.is_winner ? "#22c55e" : "#ef4444"} 
                              stroke="none" 
                              isAnimationActive={false} 
                            />
                          ))}
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="flex-1 flex items-center justify-center">
                      <LoadingState rows={3} />
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                  <ShieldAlert size={14} className="text-red-400" /> Profil de Risque (Drawdown)
                </h3>
                <div className="h-[120px] min-h-[120px] w-full bg-white/[0.01] rounded-2xl border border-white/5 p-4 flex flex-col">
                  {isReady && data?.equity_curve ? (
                    <div className="flex-1 w-full overflow-hidden">
                      <ResponsiveContainer width="99%" height="99%">
                        <AreaChart data={data.equity_curve} syncId="asset-panel">
                          <XAxis dataKey="date" hide />
                          <YAxis hide domain={['auto', 0]} />
                          <Area type="monotone" dataKey="drawdown_pct" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} isAnimationActive={false} />
                          <ReferenceLine y={0} stroke="#ffffff10" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="flex-1 bg-white/5 animate-pulse rounded-xl" />
                  )}
                </div>
              </div>

            </div>
          )}
        </div>

        <div className="p-6 bg-white/[0.02] border-t border-white/5 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-2 text-[10px] text-[--text-muted] uppercase font-bold tracking-widest">
            <Calendar size={12} /> Simulation : {new Date().toLocaleDateString()}
          </div>
          <div className="text-[10px] text-blue-400 font-bold uppercase tracking-widest flex items-center gap-2">
            <Info size={12} /> Analyse Quantitative Out-of-Sample
          </div>
        </div>
      </div>
    </div>
  );
}
