import SignalCard from './SignalCard';
import { STRATEGY_COLORS, sortSignals } from '../../utils/format';

export default function StrategySection({ strategyKey, strategyData }) {
  const colors = STRATEGY_COLORS[strategyKey] || STRATEGY_COLORS.rsi2;
  const sorted = sortSignals(strategyData.signals);

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text}`}>
          {strategyData.label}
        </span>
        <span className="text-xs text-[--text-muted]">
          {strategyData.signals.length} assets
        </span>
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
