import React, { useState, useEffect } from 'react';
import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';
import { formatPrice, formatPF, STRATEGY_LABELS, STRATEGY_COLORS, VERDICT_COLORS, getAssetType } from '../../utils/format';
import { X, ExternalLink, ShieldCheck, Activity, Target, TrendingUp, Calendar, AlertTriangle, Info, Clock, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import LoadingState from './LoadingState';
import ErrorState from './ErrorState';
import AssetIcon from './AssetIcon';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, AreaChart, Area } from 'recharts';

export default function AssetModal({ symbol, onClose }) {
  const { data, loading, error } = useApi(() => api.assetDetails(symbol), [symbol]);
  const [prices, setPrices] = useState([]);
  const [pricesLoading, setPricesLoading] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    setPricesLoading(true);
    api.assetPrices(symbol, 60)
      .then(res => {
        setPrices(res || []);
      })
      .catch(() => {
        setPrices([]);
      })
      .finally(() => {
        setPricesLoading(false);
      });
  }, [symbol]);

  if (!symbol) return null;

  const assetType = getAssetType(symbol);

  // Close on backdrop click
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div 
      className="fixed inset-0 z-[150] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in"
      onClick={handleBackdropClick}
    >
      <div className="bg-[#0f111a] border border-white/10 w-full max-w-5xl max-h-[90vh] rounded-3xl overflow-hidden shadow-2xl flex flex-col animate-slide-up">
        
        {/* Header Section */}
        <div className="relative p-6 sm:p-8 bg-gradient-to-b from-white/[0.03] to-transparent border-b border-white/5">
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
                <p className="text-sm text-[--text-muted] font-medium uppercase tracking-wider">
                  {data?.name || 'Asset analysis'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-8">
              <div className="text-right">
                <p className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mb-1">Dernier Prix</p>
                <p className="text-2xl font-mono font-bold text-white tabular-nums">
                  {data?.last_price ? formatPrice(data.last_price) : '--'}
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
            <ErrorState message={error} />
          ) : (
            <div className="space-y-10">
              
              {/* Quick Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatBox 
                  label="Score Stratégies" 
                  value={`${data?.validations?.length || 0}/3`} 
                  sub="Validations"
                  icon={<ShieldCheck size={16} className="text-green-400" />}
                />
                <StatBox 
                  label="Signaux Actifs" 
                  value={data?.signals?.filter(s => s.signal !== 'NO_SIGNAL').length || 0}
                  sub="Opportunités"
                  icon={<TrendingUp size={16} className="text-blue-400" />}
                />
                <StatBox 
                  label="Open Positions" 
                  value={data?.open_positions?.length || 0} 
                  sub={data?.open_positions?.length > 0 ? "En cours" : "Flat"}
                  icon={<Activity size={16} className={data?.open_positions?.length > 0 ? "text-green-400" : "text-[--text-muted]"} />}
                />
                <StatBox 
                  label="Win Rate" 
                  value={`${((data?.validations?.reduce((acc, v) => acc + v.win_rate, 0) / Math.max(1, data?.validations?.length || 1)) * 100).toFixed(0)}%`}
                  sub="Moyenne"
                  icon={<Target size={16} className="text-purple-400" />}
                />
              </div>

              {/* Charts Section */}
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
                <div className="xl:col-span-2 space-y-4">
                  <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                    <TrendingUp size={14} /> Performance Historique (60j)
                  </h3>
                  <div className="h-[300px] w-full bg-white/[0.02] rounded-3xl border border-white/5 p-4">
                    {pricesLoading ? (
                      <div className="h-full flex items-center justify-center"><LoadingState rows={3} /></div>
                    ) : prices && prices.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={prices}>
                          <defs>
                            <linearGradient id="colorPrice" x1="0" x2="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.1}/>
                              <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                          <XAxis 
                            dataKey="date" 
                            hide 
                          />
                          <YAxis 
                            domain={['auto', 'auto']} 
                            orientation="right"
                            tick={{ fill: '#64748b', fontSize: 10 }}
                            axisLine={false}
                            tickLine={false}
                            tickFormatter={(val) => val.toFixed(0)}
                          />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid #ffffff10', borderRadius: '12px' }}
                            itemStyle={{ color: '#fff', fontSize: '12px' }}
                            labelStyle={{ color: '#64748b', fontSize: '10px', marginBottom: '4px' }}
                          />
                          <Area 
                            type="monotone" 
                            dataKey="close" 
                            stroke="#22c55e" 
                            strokeWidth={2}
                            fillOpacity={1} 
                            fill="url(#colorPrice)" 
                            animationDuration={1500}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-full flex items-center justify-center text-[--text-muted] text-xs">Aucune donnée de prix disponible.</div>
                    )}
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                    <ShieldCheck size={14} /> Validations Stratégiques
                  </h3>
                  <div className="space-y-3">
                    {data?.validations?.length > 0 ? (
                      data.validations.map((v, i) => (
                        <ValidationCard key={i} validation={v} />
                      ))
                    ) : (
                      <div className="p-8 text-center bg-white/[0.02] border border-dashed border-white/10 rounded-3xl">
                        <Info size={24} className="mx-auto text-[--text-muted] mb-3 opacity-20" />
                        <p className="text-xs text-[--text-muted]">Aucune validation robuste pour cet actif.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Signals History Section */}
              <div className="space-y-4">
                <h3 className="text-xs font-bold text-[--text-muted] uppercase tracking-widest flex items-center gap-2">
                  <Clock size={14} /> Derniers Signaux Détectés
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {data?.signals?.length > 0 ? (
                    data.signals.map((s, i) => (
                      <div key={i} className="p-4 bg-white/[0.03] border border-white/5 rounded-2xl flex items-center justify-between group hover:bg-white/[0.05] transition-all">
                        <div>
                          <p className={`text-xs font-bold uppercase tracking-widest ${(STRATEGY_COLORS[s.strategy] || STRATEGY_COLORS[s.strategy.split('_')[0]] || {}).text}`}>
                            {STRATEGY_LABELS[s.strategy] || STRATEGY_LABELS[s.strategy.split('_')[0]] || s.strategy}
                          </p>
                          <p className="text-[10px] text-[--text-muted] mt-1 italic">{s.notes || 'Scan technique OK'}</p>
                        </div>
                        <div className="text-right">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-tighter ${s.signal === 'BUY' ? 'bg-green-500/20 text-green-400' : s.signal === 'SELL' ? 'bg-red-500/20 text-red-400' : 'bg-white/5 text-[--text-muted]'}`}>
                            {s.signal}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="col-span-3 py-12 text-center bg-white/[0.01] border border-white/5 rounded-3xl text-sm text-[--text-muted]">
                      Aucun signal récent dans les logs.
                    </div>
                  )}
                </div>
              </div>

            </div>
          )}
        </div>

        {/* Footer Action */}
        <div className="p-6 bg-white/[0.02] border-t border-white/5 flex justify-between items-center">
          <div className="flex items-center gap-2 text-[10px] text-[--text-muted] uppercase font-bold tracking-widest">
            <Calendar size={12} /> Dernière mise à jour : {new Date().toLocaleDateString()}
          </div>
          <a 
            href={`https://finance.yahoo.com/quote/${symbol}`} 
            target="_blank" 
            rel="noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-xl text-xs font-bold text-white transition-all border border-white/10"
          >
            Voir sur Yahoo Finance <ExternalLink size={14} />
          </a>
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, sub, icon }) {
  return (
    <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl hover:bg-white/[0.05] transition-all group">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">{label}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-black text-white tracking-tight">{value}</span>
        <span className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">{sub}</span>
      </div>
    </div>
  );
}

function ValidationCard({ validation }) {
  const v = VERDICT_COLORS[validation.verdict] || VERDICT_COLORS.REJECTED;
  const s = validation.strategy.split('_')[0];
  const strategyLabel = STRATEGY_LABELS[validation.strategy] || STRATEGY_LABELS[s] || validation.strategy;
  const strategyColors = STRATEGY_COLORS[validation.strategy] || STRATEGY_COLORS[s] || {};
  
  return (
    <div className="p-4 bg-white/[0.03] border border-white/5 rounded-3xl group hover:border-green-500/30 transition-all">
      <div className="flex items-center justify-between mb-4">
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest ${strategyColors.bg || 'bg-white/5'} ${strategyColors.text || 'text-white'}`}>
          {strategyLabel}
        </span>
        <span className={`px-2 py-0.5 rounded text-[9px] font-black border ${v.bg} ${v.text} ${v.border} uppercase`}>
          {validation.verdict}
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[9px] font-bold text-[--text-muted] uppercase tracking-widest mb-1">Profit Factor</p>
          <p className={`text-sm font-mono font-bold ${validation.profit_factor >= 1.5 ? 'text-green-400' : 'text-white'}`}>
            {validation.profit_factor.toFixed(2)}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[9px] font-bold text-[--text-muted] uppercase tracking-widest mb-1">Robustesse</p>
          <p className="text-sm font-mono font-bold text-white">
            {(validation.robustness_pct || 0).toFixed(0)}%
          </p>
        </div>
      </div>
      
      <div className="mt-4 w-full h-1 bg-white/5 rounded-full overflow-hidden">
        <div 
          className={`h-full ${validation.profit_factor >= 1.5 ? 'bg-green-500' : 'bg-amber-500'} transition-all duration-1000`} 
          style={{ width: `${Math.min(100, (validation.profit_factor / 2.5) * 100)}%` }} 
        />
      </div>
    </div>
  );
}
