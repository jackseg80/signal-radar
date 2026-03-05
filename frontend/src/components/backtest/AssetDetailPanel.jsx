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
    
    // Un peu de délai pour l'animation
    const timer = setTimeout(() => setIsReady(true), 300);
    
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
        <AssetIcon symbol={symbol} size="lg" />
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold text-white leading-none">{symbol}</h2>
            <span className={`text-[10px] font-black px-1.5 py-0.5 rounded ${assetType.bg} ${assetType.text} border ${assetType.border} uppercase`}>
              {assetType.label}
            </span>
          </div>
          <p className="text-xs text-[--text-muted] mt-1 font-medium">
            {data?.n_trades || 0} trades • OOS 2014-2025
          </p>
        </div>
      </div>
      <button 
        onClick={onClose}
        className="p-2 hover:bg-white/5 rounded-full transition-colors group cursor-pointer"
      >
        <X size={24} className="text-[--text-muted] group-hover:text-white" />
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

    return items.map((item, i) => (
      <div key={i} className="bg-white/[0.02] border border-white/5 p-4 rounded-2xl">
        <div className="flex items-center gap-2 mb-2">
          <item.icon size={14} className="text-[--text-muted]" />
          <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">{item.label}</span>
        </div>
        <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
        {item.sub && <div className="text-[10px] text-[--text-muted] mt-1">{item.sub}</div>}
      </div>
    ));
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-md cursor-pointer animate-fade-in"
        onClick={onClose}
      />
      
      {/* Modal Container */}
      <div className="relative w-full max-w-5xl max-h-[95vh] bg-[#1a1d27] border border-white/10 
                      rounded-3xl shadow-2xl overflow-hidden animate-zoom-in flex flex-col m-4">
        
        <div className="p-8 lg:p-10 flex flex-col h-full overflow-y-auto">
          {renderHeader()}
          {renderStrategySwitcher()}

          {loading ? (
            <div className="space-y-8 flex-1">
              <div className="h-[320px] bg-white/[0.02] animate-pulse rounded-2xl" />
              <div className="h-[160px] bg-white/[0.02] animate-pulse rounded-2xl" />
              <div className="grid grid-cols-4 gap-4">
                {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-white/[0.02] animate-pulse rounded-2xl" />)}
              </div>
            </div>
          ) : error ? (
            <div className="flex-1">
              <ErrorState message={error} />
              <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
                <p className="text-xs text-red-400">
                  L'actif <strong>{symbol}</strong> n'est peut-être pas configuré pour la stratégie <strong>{strategy}</strong>.
                </p>
              </div>
            </div>
          ) : data && data.equity_curve ? (
            <div className="space-y-8 flex-1">
              {/* Equity Chart */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-[--text-muted] flex items-center gap-2">
                    <Activity size={12} className="text-blue-400" />
                    Performance Cumulative (OOS)
                  </h3>
                  <div className="text-sm font-bold text-white">
                    {formatPrice(data.equity_curve[data.equity_curve.length - 1]?.equity)}
                    <span className={`ml-2 text-xs ${data.stats?.max_drawdown_pct > -10 ? 'text-green-400' : 'text-amber-400'}`}>
                      {data.equity_curve.length > 0 ? (((data.equity_curve[data.equity_curve.length - 1].equity - data.equity_curve[0].equity) / data.equity_curve[0].equity) * 100).toFixed(1) : 0}%
                    </span>
                  </div>
                </div>
                <div className="h-[350px] w-full bg-white/[0.01] rounded-2xl border border-white/5 p-4">
                  {isReady && (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={data.equity_curve} syncId="asset-panel" margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
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
                        
                        {/* Market Events */}
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

                        {/* Trade Dots */}
                        {data.trades.map((t, i) => (
                          <ReferenceDot
                            key={i}
                            x={t.exit_date}
                            y={equityCurveMap[t.exit_date] || data.equity_curve[0].equity}
                            r={3}
                            fill={t.is_winner ? "#22c55e" : "#ef4444"}
                            stroke="#1a1d27"
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
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-[--text-muted] flex items-center gap-2">
                  <ShieldAlert size={12} className="text-red-400" />
                  Profil de Risque (Drawdown)
                </h3>
                <div className="h-[150px] w-full bg-white/[0.01] rounded-2xl border border-white/5 p-4">
                  {isReady && (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={data.equity_curve} syncId="asset-panel" margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorDD" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis 
                          dataKey="date" 
                          hide
                        />
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

              {/* Stats Grid */}
              <div className="space-y-4 pb-10">
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-[--text-muted] flex items-center gap-2">
                  <Target size={12} className="text-green-400" />
                  Statistiques Clés
                </h3>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {renderStats()}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
