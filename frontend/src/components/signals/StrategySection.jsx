import SignalCard from './SignalCard';
import { STRATEGY_COLORS, sortSignals } from '../../utils/format';

export default function StrategySection({ strategyKey, strategyData }) {
  const colors = STRATEGY_COLORS[strategyKey] || STRATEGY_COLORS.rsi2;
  const sorted = sortSignals(strategyData.signals);

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span
          className={`px-2.5 py-1 rounded-md text-xs font-bold ${colors.bg} ${colors.text}`}
          style={{ fontFamily: "'Space Grotesk', sans-serif" }}
        >
          {strategyData.label}
        </span>
        <span className="text-xs text-[--text-muted]">{strategyData.signals.length} assets</span>
        <div className="flex-1 h-px bg-[--border-subtle]"></div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
        {sorted.map((sig) => (
          <SignalCard
            key={sig.symbol}
            symbol={sig.symbol}
            signal={sig.signal}
            close_price={sig.close_price}
            indicator_value={sig.indicator_value}
            notes={sig.notes}
          />
        ))}
      </div>
    </div>
  );
}
