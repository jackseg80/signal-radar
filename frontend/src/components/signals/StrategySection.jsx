import React, { useState } from 'react';
import SignalCard from './SignalCard';
import { STRATEGY_COLORS, sortSignals } from '../../utils/format';
import { Eye, EyeOff, Filter } from 'lucide-react';

export default function StrategySection({ strategyKey, strategyData, onSymbolClick }) {
  const [showAll, setShowAll] = useState(false);
  const colors = STRATEGY_COLORS[strategyKey] || STRATEGY_COLORS.rsi2;
  
  // Sort signals
  const allSignals = sortSignals(strategyData.signals);
  
  // Calculate how many signals are neutral/non-actionable
  const neutralSignals = allSignals.filter(sig => sig.signal === 'NO_SIGNAL' || sig.signal === 'PENDING_EXPIRED');
  const neutralCount = neutralSignals.length;

  // Filter signals for display
  const filteredSignals = showAll 
    ? allSignals 
    : allSignals.filter(sig => sig.signal !== 'NO_SIGNAL' && sig.signal !== 'PENDING_EXPIRED');

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-md text-xs font-bold ${colors.bg} ${colors.text} shadow-sm border border-white/5`}
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}
          >
            {strategyData.label}
          </span>
          <span className="text-[10px] text-[--text-muted] font-medium uppercase tracking-wider">
            {filteredSignals.length} {filteredSignals.length === 1 ? 'Signal' : 'Signals'}
            {neutralCount > 0 && !showAll && ` (+${neutralCount} hidden)`}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {neutralCount > 0 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-bold uppercase tracking-tight transition-all cursor-pointer ${
                showAll 
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' 
                  : 'bg-white/5 text-[--text-muted] border border-transparent hover:border-white/10 hover:text-[--text-secondary]'
              }`}
            >
              {showAll ? <EyeOff size={12} /> : <Eye size={12} />}
              {showAll ? 'Hide Neutral' : `Show Neutral (${neutralCount})`}
            </button>
          )}
          <div className="h-4 w-px bg-white/5"></div>
        </div>
      </div>

      {filteredSignals.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-3 gap-4">
          {filteredSignals.map((sig) => (
            <SignalCard
              key={sig.symbol}
              symbol={sig.symbol}
              name={sig.name}
              logo_url={sig.logo_url}
              signal={sig.signal}
              close_price={sig.close_price}
              indicator_value={sig.indicator_value}
              notes={sig.notes}
              onClick={() => onSymbolClick && onSymbolClick(sig.symbol)}
            />
          ))}
        </div>
      ) : (
        <div className="py-8 text-center rounded-xl border border-dashed border-white/5 bg-white/[0.01]">
          <span className="text-xs text-[--text-muted]">No active signals for this strategy.</span>
          {neutralCount > 0 && (
            <button 
              onClick={() => setShowAll(true)}
              className="ml-2 text-xs text-green-400 hover:underline cursor-pointer"
            >
              Show neutral assets ({neutralCount})
            </button>
          )}
        </div>
      )}
    </div>
  );
}
