import React, { useState, useEffect, useMemo } from 'react';
import { 
  X, 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  Clock, 
  Activity, 
  ChevronRight,
  Info,
  ExternalLink,
  Target,
  ShieldAlert
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
  ReferenceDot,
  Cell
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
import Card from '../ui/Card';
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
    const data = payload[0].payload;
    return (
      <div className="bg-[#1a1d27] border border-white/10 p-3 rounded-lg shadow-xl backdrop-blur-md">
        <p className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mb-1">{formatDate(label)}</p>
        <div className="space-y-1">
          <p className="text-sm font-bold text-white">Equity: {formatPrice(data.equity)}</p>
          <p className={`text-xs font-medium ${data.drawdown_pct < 0 ? 'text-red-400' : 'text-green-400'}`}>
            Drawdown: {data.drawdown_pct.toFixed(2)}%
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
    const handler = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    
    // Délai pour l'animation et stabiliser Recharts
    const timer = setTimeout(() => setIsReady(true), 400);
    
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = 'unset';
      clearTimeout(timer);
    };
  }, [onClose]);

  const availableStrategies = useMemo(() => {
    if (!matrixData?.[symbol]) return [strategy];
    if (typeof matrixData[symbol] === 'object' && !Array.isArray(matrixData[symbol])) {
        return Object.keys(matrixData[symbol]);
    }
    return [strategy];
  }, [matrixData, symbol, strategy]);

  const assetType = useMemo(() => getAssetType(symbol), [symbol]);

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

  const renderHeader = () => (
    <div className="flex items-start justify-between mb-6 shrink-0">
      <div className="flex items-center gap-4">
        <AssetIcon symbol={symbol} size="lg" className="shadow-2xl ring-4 ring-white/5" />
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-3xl font-black text-white tracking-tight">{symbol}</h2>
            <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border ${assetType.bg} ${assetType.text} ${assetType.border}`}>
              {assetType.label}
            </span>
          </div>
          <p className="text-sm text-[--text-muted] font-medium uppercase tracking-wider">
            Analyse de Backtest OOS 2014-2025
          </p>
        </div>
      </div>
      <button 
        onClick={onClose}
        className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl text-white transition-all cursor-pointer border border-white/5"
      >
        <X size={24} />
      </button>
    </div>
  );

  const renderStrategySwitcher = () => (
    <div className="flex flex-wrap gap-2 mb-8 p-1 bg-white/[0.02] border border-white/5 rounded-xl w-fit shrink-0">
      {availableStrategies.map((s) => (
        <button
          key={s}
          onClick={() => setStrategy(s)}
          className={`px-4 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all cursor-pointer ${
            strategy === s 
              ? 'bg-green-500 text-white shadow-[0_0_15px_rgba(34,197,94,0.3)]' 
              : 'text-[--text-muted] hover:text-white hover:bg-white/5'
          }`}
        >
          {STRATEGY_LABELS[s] || s.toUpperCase()}
        </button>
      ))}
    </div>
  );

  const renderStats = () => {
    if (!data?.stats) return null;
    const { stats } = data;
    
    const items = [
      { label: 'Max Drawdown', value: `${stats.max_drawdown_pct}%`, sub: stats.max_drawdown_date, icon: ShieldAlert, color: 'text-red-400' },
      { label: 'Meilleur Trade', value: `${stats.best_trade_pct}%`, icon: TrendingUp, color: 'text-green-400' },
      { label: 'Pire Trade', value: `${stats.worst_trade_pct}%`, icon: TrendingDown, color: 'text-red-400' },
      { label: 'Durée Moyenne', value: `${stats.avg_holding_days}j`, icon: Clock, color: 'text-blue-400' },
    ];

    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 w-full">
        {items.map((item, i) => (
          <div key={i} className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl hover:bg-white/[0.05] transition-all group">
            <div className="flex items-center gap-2 mb-3">
              <item.icon size={16} className="text-[--text-muted]" />
              <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">{item.label}</span>
            </div>
            <div className="flex flex-col">
              <span className={`text-2xl font-black tracking-tight ${item.color}`}>{item.value}</span>
              {item.sub && <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mt-1">{item.sub}</span>}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
      {/* Overlay - simple high z-index overlay */}
      <div
        className="fixed inset-0 bg-black/90 backdrop-blur-md cursor-pointer animate-fade-in"
        onClick={onClose}
      />
      
      {/* Modal Container - relative to center flex */}
      <div className="relative w-full max-w-6xl max-h-[90vh] bg-[#0f111a] border border-white/10 
                      rounded-[2.5rem] shadow-2xl overflow-hidden animate-slide-up flex flex-col">
        
        {/* Header Section (always visible) */}
        <div className="relative p-8 lg:p-10 bg-gradient-to-b from-white/[0.03] to-transparent border-b border-white/5 shrink-0">
          {renderHeader()}
          {renderStrategySwitcher()}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-8 lg:p-10 custom-scrollbar">
          {loading ? (
            <div className="space-y-10">
              <div className="grid grid-cols-4 gap-4">
                {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-white/[0.02] animate-pulse rounded-3xl" />)}
              </div>
              <div className="h-[350px] bg-white/[0.02] animate-pulse rounded-3xl" />
            </div>
          ) : error ? (
            <div className="flex-1">
              <ErrorState message={error} />
              <div className="mt-4 p-6 bg-red-500/10 border border-red-500/20 rounded-3xl">
                <p className="text-sm text-red-400">
                  L'actif <strong>{symbol}</strong> n'est peut-être pas configuré pour la stratégie <strong>{strategy}</strong> dans l'univers de production.
                </p>
              </div>
            </div>
          ) : data && data.equity_curve ? (
            <div className="space-y-12">
              
              {/* Stats Grid */}
              <div className="space-y-4">
                <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                  <Target size={14} className="text-green-400" /> Statistiques de Performance
                </h3>
                {renderStats()}
              </div>

              {/* Equity Chart */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                    <Activity size={14} className="text-blue-400" /> Courbe d'Equity Cumulative (OOS)
                  </h3>
                  <div className="text-xl font-mono font-bold text-white tabular-nums">
                    {formatPrice(data.equity_curve[data.equity_curve.length - 1]?.equity)}
                    <span className={`ml-3 text-sm ${data.stats?.max_drawdown_pct > -10 ? 'text-green-400' : 'text-amber-400'}`}>
                      {data.equity_curve.length > 0 ? (((data.equity_curve[data.equity_curve.length - 1].equity - data.equity_curve[0].equity) / data.equity_curve[0].equity) * 100).toFixed(1) : 0}%
                    </span>
                  </div>
                </div>
                
                <div className="h-[350px] w-full bg-white/[0.01] rounded-[2rem] border border-white/5 p-6 overflow-hidden">
                  {isReady && (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={data.equity_curve} syncId="asset-panel" margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                        <XAxis 
                          dataKey="date" 
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748b', fontSize: 10 }}
                          minTickGap={40}
                          tickFormatter={(str) => {
                            const date = new Date(str);
                            return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
                          }}
                        />
                        <YAxis 
                          hide={false}
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748b', fontSize: 10 }}
                          domain={['auto', 'auto']}
                          tickFormatter={(val) => `$${(val / 1000).toFixed(1)}k`}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        <Area 
                          type="monotone" 
                          dataKey="equity" 
                          stroke="#3b82f6" 
                          strokeWidth={2}
                          fillOpacity={1} 
                          fill="url(#colorEquity)" 
                          isAnimationActive={false}
                        />
                        
                        {filteredMarketEvents.map((event, i) => (
                          <ReferenceLine
                            key={i}
                            x={event.date}
                            stroke={event.color}
                            strokeDasharray="3 3"
                            label={{ 
                              value: event.label, 
                              position: 'insideTopLeft', 
                              fill: event.color, 
                              fontSize: 8,
                              fontWeight: 'bold',
                              offset: 10
                            }}
                          />
                        ))}

                        {data.trades.map((t, i) => (
                          <ReferenceDot
                            key={i}
                            x={t.exit_date}
                            y={equityCurveMap[t.exit_date] || data.equity_curve[0].equity}
                            r={3}
                            fill={t.is_winner ? "#22c55e" : "#ef4444"}
                            stroke="#0f111a"
                            strokeWidth={1}
                            isAnimationActive={false}
                          />
                        ))}
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* Drawdown Chart */}
              <div className="space-y-4">
                <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                  <ShieldAlert size={14} className="text-red-400" /> Profil de Risque (Drawdown)
                </h3>
                <div className="h-[150px] w-full bg-white/[0.01] rounded-[2rem] border border-white/5 p-6 overflow-hidden">
                  {isReady && (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={data.equity_curve} syncId="asset-panel" margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorDD" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.15}/>
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="date" hide />
                        <YAxis 
                          axisLine={false}
                          tickLine={false}
                          tick={{ fill: '#64748b', fontSize: 10 }}
                          domain={['auto', 0]}
                          tickFormatter={(val) => `${val.toFixed(0)}%`}
                        />
                        <Tooltip content={<CustomTooltip />} />
                        <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />
                        <Area 
                          type="monotone" 
                          dataKey="drawdown_pct" 
                          stroke="#ef4444" 
                          strokeWidth={1.5}
                          fillOpacity={1} 
                          fill="url(#colorDD)" 
                          isAnimationActive={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

            </div>
          ) : null}
        </div>
        
        {/* Footer */}
        <div className="p-8 bg-white/[0.02] border-t border-white/5 flex justify-between items-center shrink-0">
          <div className="flex items-center gap-2 text-[10px] text-[--text-muted] uppercase font-bold tracking-widest">
            <Calendar size={12} /> Dernière mise à jour : {new Date().toLocaleDateString()}
          </div>
          <div className="text-[10px] text-blue-400 font-bold uppercase tracking-widest">
            Mode Analyse Quantitative Out-of-Sample
          </div>
        </div>
      </div>
    </div>
  );
}
