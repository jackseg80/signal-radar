import React, { useState, useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';
import { formatPrice, SIGNAL_COLORS, STRATEGY_COLORS, STRATEGY_LABELS } from '../../utils/format';
import { X, TrendingUp, History, ShieldCheck, ExternalLink, Calendar, Activity } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

export default function AssetModal({ symbol, onClose }) {
  const { data: details, loading: loadingDetails } = useApi(() => api.assetDetails(symbol), [symbol]);
  const { data: history, loading: loadingHistory } = useApi(() => api.assetHistory(symbol, 60), [symbol]);
  const { data: prices, loading: loadingPrices } = useApi(() => api.assetPrices(symbol, 60), [symbol]);

  const historyData = useMemo(() => {
    if (!prices || !Array.isArray(prices)) return [];
    
    // Create a map of signals by date for quick lookup
    const signalMap = {};
    if (history && Array.isArray(history)) {
      history.forEach(h => {
        const date = h.timestamp.split(' ')[0];
        // Only keep important signals for the chart dots
        if (h.signal === 'BUY' || h.signal === 'SELL' || h.signal === 'SAFETY_EXIT') {
          signalMap[date] = h.signal;
        }
      });
    }

    return prices.map(p => ({
      date: p.date,
      price: p.close,
      signal: signalMap[p.date] || null
    }));
  }, [prices, history]);

  if (!symbol) return null;

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center p-4 md:p-8 bg-black/90 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-5xl max-h-[90vh] overflow-y-auto glass-card rounded-2xl shadow-2xl border border-white/10 flex flex-col">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between p-6 border-b border-white/5 bg-[--bg-card]/95 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-green-500/10 text-green-400">
              <Activity size={24} />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-black text-white tracking-tighter">{symbol}</h2>
                <span className="px-2 py-0.5 rounded bg-white/5 text-[--text-muted] text-[10px] font-bold uppercase tracking-widest">Asset Detail</span>
              </div>
              <p className="text-sm text-[--text-secondary] font-medium tabular-nums">
                Dernier prix : <span className="text-white">{details ? formatPrice(details.last_price) : '--'}</span>
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/5 text-[--text-muted] hover:text-white transition-colors cursor-pointer"
          >
            <X size={24} />
          </button>
        </div>

        <div className="p-6 md:p-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Chart & History */}
          <div className="lg:col-span-2 space-y-8">
            {/* Chart Area */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">
                <TrendingUp size={14} className="text-blue-400" />
                <span>Price History & Signals (60d)</span>
              </div>
              <div className="h-64 w-full bg-white/[0.02] rounded-xl border border-white/5 p-4 min-h-[256px]">
                {historyData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={historyData}>
                      <XAxis dataKey="date" hide />
                      <YAxis domain={['auto', 'auto']} hide />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '10px' }}
                        itemStyle={{ color: '#fff' }}
                        labelStyle={{ color: '#64748b', marginBottom: '4px' }}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="price" 
                        stroke="#3b82f6" 
                        strokeWidth={2} 
                        dot={(props) => {
                          const { cx, cy, payload } = props;
                          if (payload.signal === 'BUY') return <circle key={`buy-${payload.date}`} cx={cx} cy={cy} r={5} fill="#22c55e" stroke="white" strokeWidth={1} />;
                          if (payload.signal === 'SELL' || payload.signal === 'SAFETY_EXIT') return <circle key={`sell-${payload.date}`} cx={cx} cy={cy} r={5} fill="#ef4444" stroke="white" strokeWidth={1} />;
                          return null;
                        }}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-[--text-muted] text-xs">
                    {loadingPrices ? "Chargement des prix..." : "Données de prix non disponibles"}
                  </div>
                )}
              </div>
            </div>

            {/* Strategy Status Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {details?.signals && details.signals.length > 0 ? details.signals.map(sig => {
                const colors = STRATEGY_COLORS[sig.strategy] || STRATEGY_COLORS.rsi2;
                const sigColor = SIGNAL_COLORS[sig.signal] || SIGNAL_COLORS.NO_SIGNAL;
                return (
                  <div key={sig.strategy} className="p-4 rounded-xl bg-white/5 border border-white/5 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${colors.bg} ${colors.text}`}>
                        {STRATEGY_LABELS[sig.strategy] || sig.strategy}
                      </span>
                      <span className={`text-[10px] font-bold uppercase ${sigColor.text}`}>
                        {sig.signal}
                      </span>
                    </div>
                    <div className="flex justify-between items-end">
                      <div className="space-y-1">
                        <span className="text-[10px] text-[--text-muted] uppercase">Indicateur</span>
                        <div className="text-xl font-bold text-white tabular-nums">
                          {sig.indicator_value ? Number(sig.indicator_value).toFixed(2) : '--'}
                        </div>
                      </div>
                      {sig.notes && (
                        <div className="text-[10px] text-[--text-muted] italic max-w-[120px] truncate text-right" title={sig.notes}>
                          {sig.notes}
                        </div>
                      )}
                    </div>
                  </div>
                );
              }) : (
                <div className="col-span-2 py-8 text-center bg-white/5 rounded-xl border border-white/5 text-[--text-muted] text-xs">
                  Aucun signal récent détecté.
                </div>
              )}
            </div>
          </div>

          {/* Right Sidebar: Backtest & Stats */}
          <div className="space-y-8">
            {/* Performance Validée */}
            <div className="space-y-4">
               <div className="flex items-center gap-2 text-[10px] font-bold text-[--text-muted] uppercase tracking-widest">
                  <ShieldCheck size={14} className="text-green-400" />
                  <span>Performance Validée (OOS)</span>
               </div>
               <div className="space-y-3">
                 {details?.validations && details.validations.length > 0 ? details.validations.map(v => (
                   <div key={`${v.strategy}-${v.symbol}`} className="p-4 rounded-xl bg-green-500/[0.03] border border-green-500/10 space-y-2">
                     <div className="flex justify-between items-center">
                       <span className="text-xs font-bold text-white uppercase">{STRATEGY_LABELS[v.strategy.split('_')[0]] || v.strategy}</span>
                       <span className="text-[10px] font-bold text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded">VALIDATED</span>
                     </div>
                     <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-[10px] text-[--text-muted]">Profit Factor</div>
                          <div className="text-sm font-bold text-white">{Number(v.profit_factor).toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-[--text-muted]">Win Rate</div>
                          <div className="text-sm font-bold text-white">{Math.round(v.win_rate * 100)}%</div>
                        </div>
                     </div>
                   </div>
                 )) : (
                   <div className="p-4 rounded-xl border border-dashed border-white/10 text-center">
                     <span className="text-xs text-[--text-muted]">Aucun backtest validé pour cet asset.</span>
                   </div>
                 )}
               </div>
            </div>

            {/* Positions Actuelles */}
            {details?.open_positions && details.open_positions.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-[10px] font-bold text-amber-400 uppercase tracking-widest">
                    <Calendar size={14} />
                    <span>Positions Ouvertes</span>
                </div>
                {details.open_positions.map(p => (
                  <div key={p.id} className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold text-white">{STRATEGY_LABELS[p.strategy] || p.strategy}</span>
                      <span className="text-[10px] text-[--text-muted] tabular-nums">{p.entry_date}</span>
                    </div>
                    <div className="flex justify-between items-center">
                       <div className="text-xs text-white tabular-nums">${p.entry_price}</div>
                       <div className={`text-xs font-bold tabular-nums ${p.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                         {p.unrealized_pnl >= 0 ? '+' : ''}{Number(p.unrealized_pnl).toFixed(2)}$
                       </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer actions */}
        <div className="p-6 border-t border-white/5 bg-white/[0.02] flex justify-end gap-3">
          <button 
            className="px-4 py-2 rounded-lg bg-white/5 text-[--text-muted] hover:text-white hover:bg-white/10 text-sm font-bold transition-all cursor-pointer flex items-center gap-2"
            onClick={() => window.open(`https://finance.yahoo.com/quote/${symbol}`, '_blank')}
          >
            <ExternalLink size={16} />
            Yahoo Finance
          </button>
          <button 
            onClick={onClose}
            className="px-6 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/30 rounded-lg text-sm font-bold transition-all cursor-pointer"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
}
