import React, { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
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
    
    // Safety delay for Recharts calculations
    const timer = setTimeout(() => setIsReady(true), 800);
    
    return () => {
      document.body.style.overflow = 'unset';
      clearTimeout(timer);
    };
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

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  // On utilise un Portal pour injecter le modal au sommet du DOM (dans body)
  // pour éviter les conflits de transform/z-index des parents.
  return createPortal(
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/90 backdrop-blur-xl p-4 sm:p-10 animate-fade-in"
      style={{ isolation: 'isolate' }}
      onClick={handleBackdropClick}
    >
      <div className="bg-[#0f111a] border border-white/10 w-full max-w-6xl max-h-[90vh] rounded-[2.5rem] shadow-[0_0_100px_rgba(0,0,0,0.8)] flex flex-col relative overflow-hidden animate-slide-up">
        
        {/* Header Section */}
        <div className="relative p-8 bg-gradient-to-b from-white/[0.05] to-transparent border-b border-white/5 shrink-0">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
            <div className="flex items-center gap-6">
              <AssetIcon symbol={symbol} size="lg" className="shadow-2xl ring-4 ring-white/5" />
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h2 className="text-4xl font-black text-white tracking-tighter">{symbol}</h2>
                  <span className={`px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-widest border ${assetType.bg} ${assetType.text} ${assetType.border}`}>
                    {assetType.label}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 mt-4">
                  {availableStrategies.map((s) => (
                    <button
                      key={s}
                      onClick={() => {
                        setIsReady(false);
                        setStrategy(s);
                      }}
                      className={`px-5 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border-2 ${
                        strategy === s 
                          ? 'bg-white text-black border-white' 
                          : 'bg-white/5 border-white/5 text-[--text-muted] hover:text-white hover:bg-white/10'
                      }`}
                    >
                      {STRATEGY_LABELS[s] || s.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-10">
              <div className="text-right hidden md:block">
                <p className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mb-1">Total Trades</p>
                <p className="text-3xl font-mono font-bold text-white tabular-nums">
                  {data?.n_trades ?? '--'}
                </p>
              </div>
              <button 
                onClick={onClose}
                className="p-4 bg-white/5 hover:bg-red-500 hover:text-white rounded-2xl text-[--text-muted] transition-all cursor-pointer border border-white/5 group"
              >
                <X size={28} />
              </button>
            </div>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-8 lg:p-12 custom-scrollbar bg-[#0f111a]">
          {loading ? (
            <div className="space-y-10">
              <div className="grid grid-cols-4 gap-6">
                {[1, 2, 3, 4].map(i => <div key={i} className="h-28 bg-white/[0.02] animate-pulse rounded-3xl" />)}
              </div>
              <div className="h-[400px] bg-white/[0.02] animate-pulse rounded-[2.5rem]" />
            </div>
          ) : error ? (
            <div className="space-y-6 py-10">
              <ErrorState message={error} />
              <div className="p-8 bg-red-500/10 border border-red-500/20 rounded-[2rem] text-center">
                <p className="text-red-400 font-medium text-lg mb-2 flex items-center justify-center gap-3">
                  <ShieldAlert size={24} /> Configuration manquante
                </p>
                <p className="text-red-400/60 max-w-md mx-auto">
                  L'actif <strong>{symbol}</strong> n'est pas présent dans l'univers de production de la stratégie <strong>{strategy}</strong>.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-12">
              
              {/* Stats Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
                <StatBox label="Max Drawdown" value={`${data?.stats?.max_drawdown_pct}%`} sub={data?.stats?.max_drawdown_date} color="text-red-400" icon={<ShieldAlert size={20} />} />
                <StatBox label="Meilleur Trade" value={`+${data?.stats?.best_trade_pct}%`} color="text-green-400" icon={<TrendingUp size={20} />} />
                <StatBox label="Pire Trade" value={`${data?.stats?.worst_trade_pct}%`} color="text-red-400" icon={<TrendingDown size={20} />} />
                <StatBox label="Durée Moyenne" value={`${data?.stats?.avg_holding_days}j`} color="text-blue-400" icon={<Clock size={20} />} />
              </div>

              {/* Chart Section */}
              <div className="space-y-6">
                <div className="flex items-center justify-between px-2">
                  <h3 className="text-sm font-bold text-[--text-muted] uppercase tracking-[0.2em] flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" />
                    Performance Cumulative (OOS 2014-2025)
                  </h3>
                  <div className="text-2xl font-mono font-bold text-white flex items-baseline gap-3">
                    <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">Final Equity</span>
                    {formatPrice(data?.equity_curve?.[data?.equity_curve?.length - 1]?.equity)}
                  </div>
                </div>
                
                <div className="h-[450px] min-h-[450px] w-full bg-white/[0.02] rounded-[3rem] border border-white/5 p-8 flex flex-col relative shadow-inner">
                  {isReady ? (
                    <div className="flex-1 w-full overflow-hidden">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data?.equity_curve} syncId="asset-panel" margin={{ top: 20, right: 20, left: 0, bottom: 0 }}>
                          <defs>
                            <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                          <XAxis dataKey="date" hide />
                          <YAxis 
                            domain={['auto', 'auto']} 
                            orientation="right"
                            tick={{ fill: '#64748b', fontSize: 10, fontWeight: 600 }}
                            axisLine={false}
                            tickLine={false}
                            tickFormatter={(val) => `$${(val / 1000).toFixed(1)}k`}
                          />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid #ffffff10', borderRadius: '16px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)' }}
                            itemStyle={{ color: '#fff', fontWeight: 700 }}
                          />
                          <Area 
                            type="monotone" 
                            dataKey="equity" 
                            stroke="#3b82f6" 
                            strokeWidth={4}
                            fillOpacity={1} 
                            fill="url(#colorEquity)" 
                            isAnimationActive={false}
                          />
                          {MARKET_EVENTS.map((event, i) => (
                            <ReferenceLine 
                              key={i} 
                              x={event.date} 
                              stroke={event.color} 
                              strokeDasharray="4 4" 
                              label={{ value: event.label, fill: event.color, fontSize: 10, fontWeight: 800, position: 'insideTopLeft', offset: 15 }} 
                            />
                          ))}
                          {data?.trades?.map((t, i) => (
                            <ReferenceDot 
                              key={i} 
                              x={t.exit_date} 
                              y={equityCurveMap[t.exit_date] || data.equity_curve[0].equity} 
                              r={4} 
                              fill={t.is_winner ? "#22c55e" : "#ef4444"} 
                              stroke="#0f111a" 
                              strokeWidth={2}
                              isAnimationActive={false} 
                            />
                          ))}
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center gap-4">
                      <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                      <p className="text-xs text-[--text-muted] font-bold uppercase tracking-widest animate-pulse">Initialisation du moteur graphique...</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-6">
                <h3 className="text-sm font-bold text-[--text-muted] uppercase tracking-[0.2em] flex items-center gap-3 px-2">
                  <div className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]" />
                  Profil de Risque (Drawdown)
                </h3>
                <div className="h-[150px] min-h-[150px] w-full bg-white/[0.01] rounded-[2rem] border border-white/5 p-6 flex flex-col shadow-inner">
                  {isReady ? (
                    <div className="flex-1 w-full overflow-hidden">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data?.equity_curve} syncId="asset-panel">
                          <XAxis dataKey="date" hide />
                          <YAxis hide domain={['auto', 0]} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid #ffffff10', borderRadius: '12px' }}
                          />
                          <Area type="monotone" dataKey="drawdown_pct" stroke="#ef4444" strokeWidth={2} fill="#ef4444" fillOpacity={0.15} isAnimationActive={false} />
                          <ReferenceLine y={0} stroke="#ffffff10" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="flex-1 bg-white/[0.02] animate-pulse rounded-2xl" />
                  )}
                </div>
              </div>

            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-8 bg-white/[0.03] border-t border-white/5 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-3 text-xs text-[--text-muted] font-bold tracking-wider">
            <Calendar size={16} className="text-blue-500" /> SIMULATION GÉNÉRÉE LE {new Date().toLocaleDateString('fr-FR').toUpperCase()}
          </div>
          <div className="px-4 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-full text-[10px] text-blue-400 font-black uppercase tracking-[0.2em]">
            Signal Radar Quant v2.0
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

function StatBox({ label, value, sub, icon, color }) {
  return (
    <div className="p-7 bg-white/[0.03] border border-white/5 rounded-[2rem] hover:bg-white/[0.06] transition-all group border-b-4 border-b-transparent hover:border-b-blue-500/50">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-3 bg-white/5 rounded-2xl text-[--text-muted] group-hover:scale-110 group-hover:text-white transition-all">{icon}</div>
        <span className="text-[11px] font-black text-[--text-muted] uppercase tracking-[0.15em]">{label}</span>
      </div>
      <div className="flex flex-col gap-1">
        <span className={`text-3xl font-black tracking-tighter ${color}`}>{value}</span>
        {sub && <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest opacity-60">{sub}</span>}
      </div>
    </div>
  );
}
