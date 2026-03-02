import { useApi } from '../hooks/useApi';
import { useRefresh } from '../hooks/useRefresh.jsx';
import { api } from '../api/client';
import Card from '../components/ui/Card';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import EmptyState from '../components/ui/EmptyState';
import StrategyBreakdown from '../components/performance/StrategyBreakdown';
import StrategySection from '../components/signals/StrategySection';
import OpenPositions from '../components/positions/OpenPositions';
import ClosedTrades from '../components/positions/ClosedTrades';
import EquityCurve from '../components/performance/EquityCurve';
import MarketOverview from '../components/market/MarketOverview';

function SignalsPanel() {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.signalsToday(), [refreshKey]);

  if (loading) return <Card title="Today's Signals"><LoadingState rows={4} /></Card>;
  if (error) return <Card title="Today's Signals"><ErrorState message={error} onRetry={refetch} /></Card>;

  const strategies = data?.strategies;
  if (!strategies || Object.keys(strategies).length === 0) {
    return (
      <Card title="Today's Signals">
        <EmptyState message="No signals yet. Run the scanner first: python scripts/daily_scanner.py" />
      </Card>
    );
  }

  return (
    <Card title="Today's Signals">
      <div className="space-y-6">
        {Object.entries(strategies).map(([key, strat]) => (
          <StrategySection key={key} strategyKey={key} strategyData={strat} />
        ))}
      </div>
    </Card>
  );
}

export default function Dashboard() {
  return (
    <div className="space-y-6">
      <StrategyBreakdown />
      <SignalsPanel />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <OpenPositions />
        <ClosedTrades />
      </div>
      <EquityCurve />
      <MarketOverview />
    </div>
  );
}
