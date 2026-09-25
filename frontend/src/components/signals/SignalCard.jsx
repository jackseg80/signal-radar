import { cn } from "../../lib/utils";
import { formatPrice, SIGNAL_COLORS, getAssetType } from '../../utils/format';
import { ArrowUpCircle, ArrowDownCircle, AlertCircle, Eye, Timer } from 'lucide-react';
import AssetIcon from '../ui/AssetIcon';

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

export default function SignalCard({ symbol, name, logo_url, signal, close_price, indicator_value, notes, technical_signal, eligibility, source_session, target_session, max_budget_usd, indicative_shares, paper_signal, paper_status, paper_reasons = [], paper_warnings = [], paper_budget_usd, paper_indicative_shares, onClick }) {
  const colors = SIGNAL_COLORS[signal] || SIGNAL_COLORS.NO_SIGNAL;
  const isActionable = signal === 'BUY' || signal === 'SELL' || signal === 'SAFETY_EXIT';
  const isWatch = signal === 'WATCH' || signal === 'PENDING_VALID';
  const paperActive = ['BUY', 'SELL', 'SAFETY_EXIT', 'HOLD'].includes(paper_signal);
  const isDim = (signal === 'NO_SIGNAL' || signal === 'PENDING_EXPIRED') && !paperActive;
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
      {/* Signal badge: overflow top-right, overlapping the card border */}
      <div className={cn(
        "absolute top-0 right-0 px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1.5 uppercase transition-colors z-10 -mr-px -mt-px",
        colors.bg, colors.text
      )}>
        {icon}
        {signal === 'NO_SIGNAL' ? '---' : signal.replace('_', ' ')}
      </div>

      {/* Symbol + Asset type */}
      <div className="flex items-center gap-3 min-w-0">
        <AssetIcon symbol={symbol} logoUrl={logo_url} size="sm" />
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-2">
            <h3 className={cn(
              "text-sm tracking-tight",
              isActionable ? "font-bold text-white" : "font-semibold text-[--text-secondary]"
            )}>
              {symbol}
            </h3>
            <span className={`text-[7px] font-black px-1 rounded ${assetType.bg} ${assetType.text} border ${assetType.border} uppercase`}>
              {assetType.label}
            </span>
          </div>
          {name && <div className="text-[9px] text-[--text-muted] truncate max-w-[100px]">{name}</div>}
        </div>
      </div>

      <div className="flex items-baseline justify-between mt-3">
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
      {technical_signal === 'BUY' && (
        <div className="mt-2 text-[10px] text-[--text-secondary]">
          <div>Signal détecté {source_session} · ouverture visée {target_session}</div>
          <div className={eligibility === 'ELIGIBLE' ? 'text-green-400' : 'text-amber-400'}>
            {eligibility === 'ELIGIBLE' ? 'Achat possible' : eligibility === 'EXPIRED' ? 'Signal expiré' : 'Achat réel bloqué'}
          </div>
          {eligibility === 'ELIGIBLE' && (
            <div>Budget maximal {Number(max_budget_usd).toFixed(2)} USD · {indicative_shares} action(s) indicatives. Prix du marché non garanti.</div>
          )}
        </div>
      )}
      {eligibility === 'DATA_MISSING' && <div className="mt-2 text-[10px] text-red-400">Donnée manquante</div>}
      {paper_status && paper_status !== 'NO_SIGNAL' && (
        <div className="mt-2 border-t border-white/5 pt-2 text-[10px] text-blue-300">
          <div>Simulation papier autonome : {{
            PENDING_BUY: 'achat préparé',
            PENDING_SELL: 'vente préparée',
            HOLD: 'position conservée',
            BLOCKED: 'aucun achat papier',
            MERGED: 'motif regroupé',
          }[paper_status] || paper_status}</div>
          {paper_status === 'PENDING_BUY' && paper_budget_usd != null && (
            <div>Budget papier {Number(paper_budget_usd).toFixed(2)} USD · {paper_indicative_shares} action(s) indicatives</div>
          )}
          {paper_reasons.length > 0 && <div className="text-[--text-muted]">{paper_reasons.join(' ; ')}</div>}
          {paper_warnings.length > 0 && <div className="text-amber-300">{paper_warnings.join(' ; ')}</div>}
        </div>
      )}
      
      {/* Hover decoration */}
      <div className="absolute inset-x-0 bottom-0 h-0.5 bg-gradient-to-r from-transparent via-green-500/0 to-transparent group-hover:via-green-500/30 transition-all duration-500 rounded-b-xl" />
    </div>
  );
}
