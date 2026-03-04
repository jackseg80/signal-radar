import { cn } from "../../lib/utils";
import { formatPrice, SIGNAL_COLORS, getAssetType } from '../../utils/format';
import { ArrowUpCircle, ArrowDownCircle, AlertCircle, Eye, Timer } from 'lucide-react';

const SIGNAL_GLOW = {
  BUY: 'glow-green',
  SELL: 'glow-red',
  SAFETY_EXIT: 'glow-red',
  WATCH: 'glow-amber',
  PENDING_VALID: 'glow-amber',
};

const SIGNAL_ICONS = {
  BUY: <ArrowUpCircle size={14} className="text-green-400" />,
  SELL: <ArrowDownCircle size={14} className="text-red-400" />,
  SAFETY_EXIT: <AlertCircle size={14} className="text-red-400" />,
  HOLD: <Timer size={14} className="text-blue-400" />,
  WATCH: <Eye size={14} className="text-amber-400" />,
};

export default function SignalCard({ symbol, signal, close_price, indicator_value, notes, onClick }) {
  const colors = SIGNAL_COLORS[signal] || SIGNAL_COLORS.NO_SIGNAL;
  const isActionable = signal === 'BUY' || signal === 'SELL' || signal === 'SAFETY_EXIT';
  const isWatch = signal === 'WATCH' || signal === 'PENDING_VALID';
  const isDim = signal === 'NO_SIGNAL' || signal === 'PENDING_EXPIRED';
  const glowClass = SIGNAL_GLOW[signal] || '';
  const icon = SIGNAL_ICONS[signal];
  
  const assetType = getAssetType(symbol);

  return (
    <div 
      onClick={onClick}
      className={cn(
        "group relative rounded-xl border border-[--glass-border] p-4 transition-all duration-300 cursor-pointer",
        "hover:scale-[1.03] hover:border-white/20 active:scale-[0.98]",
        (isActionable || isWatch) ? `glass-card ${glowClass}` : 'bg-white/[0.02] shadow-sm',
        isActionable && signal === 'BUY' && 'animate-border-glow',
        isDim && 'opacity-30 grayscale-[0.5]'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className={cn(
            "text-sm tracking-tight",
            isActionable ? "font-bold text-white" : "font-semibold text-[--text-secondary]"
          )}>
            {symbol}
          </h3>
          <span className={`text-[8px] font-black px-1 rounded ${assetType.bg} ${assetType.text} border ${assetType.border} uppercase`}>
            {assetType.label}
          </span>
        </div>
        
        <div className={cn(
          "px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1.5 uppercase transition-colors",
          colors.bg, colors.text
        )}>
          {icon}
          {signal === 'NO_SIGNAL' ? '---' : signal.replace('_', ' ')}
        </div>
      </div>

      <div className="flex items-baseline justify-between">
        <div className="text-sm font-medium tabular-nums text-[--text-secondary]">
          {close_price != null ? formatPrice(close_price) : '--'}
        </div>
        
        {indicator_value != null && (
          <div className="text-[10px] text-[--text-muted] tabular-nums bg-white/5 px-1.5 py-0.5 rounded">
             Ind: {Number(indicator_value).toFixed(1)}
          </div>
        )}
      </div>

      {notes && (
        <div 
          className="mt-3 text-[10px] text-[--text-muted] border-t border-white/5 pt-2 italic truncate hover:whitespace-normal transition-all" 
          title={notes}
        >
          {notes}
        </div>
      )}
      
      {/* Hover decoration */}
      <div className="absolute inset-x-0 bottom-0 h-0.5 bg-gradient-to-r from-transparent via-green-500/0 to-transparent group-hover:via-green-500/30 transition-all duration-500 rounded-b-xl" />
    </div>
  );
}
