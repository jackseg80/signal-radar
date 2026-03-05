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

const TradeTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const t = payload[0].payload;
    return (
      <div className="bg-[#1a1d27] border border-white/10 p-3 rounded-lg shadow-xl backdrop-blur-md">
        <div className="flex items-center justify-between gap-4 mb-2">
          <span className={`text-[8px] font-black px-1.5 py-0.5 rounded uppercase ${t.is_winner ? 'bg-green-500/20 text-green-400 border border-green-500/20' : 'bg-red-500/20 text-red-400 border border-red-500/20'}`}>
            {t.is_winner ? 'Winner' : 'Loser'}
          </span>
          <span className="text-[10px] text-[--text-muted]">{t.entry_date} → {t.exit_date}</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          <span className="text-[10px] text-[--text-muted]">Return</span>
          <span className={`text-xs font-bold text-right ${t.is_winner ? 'text-green-400' : 'text-red-400'}`}>{formatPct(t.return_pct)}</span>
          <span className="text-[10px] text-[--text-muted]">PnL</span>
          <span className={`text-[10px] font-medium text-right ${t.is_winner ? 'text-green-400' : 'text-red-400'}`}>{formatPnl(t.pnl)}</span>
          <span className="text-[10px] text-[--text-muted]">Price</span>
          <span className="text-[10px] text-white text-right">{t.entry_price} → {t.exit_price}</span>
        </div>
      </div>
    );
  }
  return null;
};

export default function AssetDetailPanel({ symbol, initialStrategy, matrixData, onClose }) {
  const [strategy, setStrategy] = useState(initialStrategy);

  const { data, loading, error } = useApi(
    () => api.backtestEquityCurve(strategy, symbol),
    [symbol, strategy]
  );

  // Fermeture sur Escape
  useEffect(() => {
    const handler = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const availableStrategies = useMemo(() => {
    if (!matrixData?.[symbol]) return [strategy];
    return Object.keys(matrixData[symbol]);
  }, [matrixData, symbol]);

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
    <div className="flex items-start justify-between mb-6">
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
        className="p-2 hover:bg-white/5 rounded-full transition-colors group"
      >
        <X size={20} className="text-[--text-muted] group-hover:text-white" />
      </button>
    </div>
  );

  const renderStrategySwitcher = () => (
    <div className="flex flex-wrap gap-2 mb-8 p-1 bg-white/[0.02] border border-white/5 rounded-xl w-fit">
      {availableStrategies.map((s) => (
        <button
          key={s}
          onClick={() => setStrategy(s)}
          className={`px-4 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${
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
      <div className="grid grid-cols-2 gap-4">
        {items.map((item, i) => (
          <div key={i} className="bg-white/[0.02] border border-white/5 p-4 rounded-2xl">
            <div className="flex items-center gap-2 mb-2">
              <item.icon size={14} className="text-[--text-muted]" />
              <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">{item.label}</span>
            </div>
            <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
            {item.sub && <div className="text-[10px] text-[--text-muted] mt-1">{item.sub}</div>}
          </div>
        ))}
      </div>
    );
  };

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] animate-fade-in"
        onClick={onClose}
      />
      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-[520px] bg-[#1a1d27]
                      border-l border-white/10 z-[70] overflow-y-auto
                      animate-slide-in-right p-8 shadow-2xl flex flex-col min-h-screen">
        {renderHeader()}
        {renderStrategySwitcher()}

        {loading ? (
          <div className="space-y-8 flex-1">
            <div className="h-[220px] bg-white/[0.02] animate-pulse rounded-2xl" />
            <div className="h-[120px] bg-white/[0.02] animate-pulse rounded-2xl" />
            <div className="grid grid-cols-2 gap-4">
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
          <div className="space-y-8 flex-1 pb-10">
            {/* Equity Chart */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-[--text-muted] flex items-center gap-2">
                  <Activity size={12} className="text-blue-400" />
                  Performance Cumulative
                </h3>
                <div className="text-sm font-bold text-white">
                  {formatPrice(data.equity_curve[data.equity_curve.length - 1]?.equity)}
                  <span className={`ml-2 text-xs ${data.stats?.max_drawdown_pct > -10 ? 'text-green-400' : 'text-amber-400'}`}>
                    {data.equity_curve.length > 0 ? (((data.equity_curve[data.equity_curve.length - 1].equity - data.equity_curve[0].equity) / data.equity_curve[0].equity) * 100).toFixed(1) : 0}%
                  </span>
                </div>
              </div>
              <div className="h-[240px] w-full bg-white/[0.01] rounded-2xl border border-white/5 p-4 min-h-[240px]">
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
                      minTickGap={30}
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
              </div>
            </div>

            {/* Drawdown Chart */}
            <div className="space-y-4">
              <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-[--text-muted] flex items-center gap-2">
                <ShieldAlert size={12} className="text-red-400" />
                Profil de Risque (Drawdown)
              </h3>
              <div className="h-[140px] w-full bg-white/[0.01] rounded-2xl border border-white/5 p-4">
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
              </div>
            </div>

            {/* Stats Grid */}
            <div className="space-y-4">
              <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-[--text-muted] flex items-center gap-2">
                <Target size={12} className="text-green-400" />
                Statistiques Clés
              </h3>
              {renderStats()}
            </div>
            
            <div className="pt-4 pb-8">
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-4 flex gap-4">
                <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center shrink-0">
                  <Info size={20} className="text-blue-400" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white mb-1">Analyse OOS</h4>
                  <p className="text-[10px] text-blue-100/60 leading-relaxed">
                    Les résultats affichés sont "Out-of-Sample", simulant la performance réelle si la stratégie avait été lancée en 2014 avec les paramètres optimisés sur la période précédente.
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </>
  );
}
