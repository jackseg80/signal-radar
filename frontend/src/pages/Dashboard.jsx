import { useState } from 'react';
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
import NearTrigger from '../components/signals/NearTrigger';
import LivePositions from '../components/live/LivePositions';
import PaperVsLive from '../components/live/PaperVsLive';
import LiveTradeForm from '../components/live/LiveTradeForm';
import { LayoutDashboard, Activity } from 'lucide-react';

function SignalsPanel({ className }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.signalsToday(), [refreshKey]);

  if (loading) return <Card title="Today's Signals" className={className}><LoadingState rows={4} /></Card>;
  if (error) return <Card title="Today's Signals" className={className}><ErrorState message={error} onRetry={refetch} /></Card>;

  const strategies = data?.strategies;
  if (!strategies || Object.keys(strategies).length === 0) {
    return (
      <Card title="Today's Signals" className={className}>
        <EmptyState message="No signals yet. Run the scanner first." />
      </Card>
    );
  }

  return (
    <Card title="Today's Signals" subtitle="Active strategy scanner results" className={className}>
      <div className="space-y-6">
        {Object.entries(strategies).map(([key, strat]) => (
          <StrategySection key={key} strategyKey={key} strategyData={strat} />
        ))}
      </div>
    </Card>
  );
}

export default function Dashboard() {
  const [showTradeForm, setShowTradeForm] = useState(false);
  const { refresh } = useRefresh();

  // Flexible height: grow with content, but scroll if too long
  const cardClass = "h-auto max-h-[600px] overflow-hidden flex flex-col animate-slide-up transition-all duration-300";

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-white/5 pb-4">
        <div>
          <h1 
            className="text-2xl font-bold text-white tracking-tight flex items-center gap-3"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}
          >
            <LayoutDashboard className="text-green-400" size={28} />
            Command Center
          </h1>
          <p className="text-sm text-[--text-muted] mt-1">Real-time signal monitoring and portfolio performance.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setShowTradeForm({})}
            className="px-4 py-2 rounded-lg bg-green-500/10 text-green-400 border border-green-500/20 text-sm font-medium hover:bg-green-500/20 transition-all flex items-center gap-2 cursor-pointer"
          >
            <Activity size={16} />
            Log Live Trade
          </button>
        </div>
      </div>

      {/* 1. KPIs (Full Width) */}
      <div className="animate-slide-up" style={{ animationDelay: '0ms' }}>
        <StrategyBreakdown />
      </div>

      {/* 2. Main Grid - 3 Columns (Responsive) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        
        {/* COL 1: ALERTS & MONITORING */}
        <div className="space-y-6">
           <NearTrigger className={cardClass} />
           <LivePositions className={cardClass} />
        </div>

        {/* COL 2: SIGNALS & ANALYTICS */}
        <div className="space-y-6">
           <SignalsPanel className={cardClass} />
           <EquityCurve className={cardClass} />
        </div>

        {/* COL 3: PORTFOLIO & HISTORY */}
        <div className="space-y-6">
           <OpenPositions 
             onLogReal={(prefill) => setShowTradeForm(prefill || true)} 
             className={cardClass} 
           />
           <ClosedTrades className={cardClass} />
        </div>
      </div>

      {/* 3. Market Overview (Full Width) */}
      <div className="animate-slide-up" style={{ animationDelay: '200ms' }}>
        <MarketOverview />
      </div>

      {/* 4. Comparison Analysis (Full Width) */}
      <div className="animate-slide-up" style={{ animationDelay: '300ms' }}>
        <PaperVsLive />
      </div>

      {showTradeForm && (
        <LiveTradeForm
          prefill={typeof showTradeForm === 'object' ? showTradeForm : {}}
          onDone={() => { setShowTradeForm(false); refresh(); }}
          onCancel={() => setShowTradeForm(false)}
        />
      )}
    </div>
  );
}
