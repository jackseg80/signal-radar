import { useState, useMemo } from 'react';
import { Responsive, WidthProvider } from 'react-grid-layout/legacy';
import { useApi } from '../hooks/useApi';
import { useRefresh } from '../hooks/useRefresh.jsx';
import { useAssetView } from '../hooks/useAssetView.jsx';
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
import { LayoutDashboard, Activity, RotateCcw } from 'lucide-react';

const ResponsiveGridLayout = WidthProvider(Responsive);

function SignalsPanel({ className, onSymbolClick }) {
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
    <Card 
      title="Today's Signals" 
      subtitle="Active strategy scanner results" 
      className={className}
      noScroll
    >
      <div className="space-y-6">
        {Object.entries(strategies).map(([key, strat]) => (
          <StrategySection key={key} strategyKey={key} strategyData={strat} onSymbolClick={onSymbolClick} />
        ))}
      </div>
    </Card>
  );
}

const DEFAULT_LAYOUTS = {
  lg: [
    { i: 'kpi', x: 0, y: 0, w: 12, h: 6, static: false },
    { i: 'near', x: 0, y: 6, w: 4, h: 12 },
    { i: 'signals', x: 0, y: 18, w: 4, h: 20 },
    { i: 'open-pos', x: 4, y: 6, w: 8, h: 12 },
    { i: 'equity', x: 4, y: 18, w: 4, h: 10 },
    { i: 'trades', x: 8, y: 18, w: 4, h: 10 },
    { i: 'live-pos', x: 4, y: 28, w: 8, h: 10 },
    { i: 'market', x: 0, y: 38, w: 12, h: 15 },
    { i: 'comparison', x: 0, y: 53, w: 12, h: 10 },
  ],
  md: [
    { i: 'kpi', x: 0, y: 0, w: 10, h: 6 },
    { i: 'near', x: 0, y: 6, w: 5, h: 10 },
    { i: 'signals', x: 5, y: 6, w: 5, h: 20 },
    { i: 'open-pos', x: 0, y: 16, w: 10, h: 10 },
    { i: 'equity', x: 0, y: 26, w: 5, h: 10 },
    { i: 'trades', x: 5, y: 26, w: 5, h: 10 },
    { i: 'live-pos', x: 0, y: 36, w: 10, h: 10 },
    { i: 'market', x: 0, y: 46, w: 10, h: 15 },
    { i: 'comparison', x: 0, y: 61, w: 10, h: 10 },
  ]
};

export default function Dashboard() {
  const [showTradeForm, setShowTradeForm] = useState(false);
  const { openAsset } = useAssetView();
  const { refresh } = useRefresh();
  
  const initialLayouts = useMemo(() => {
    const saved = localStorage.getItem('dashboard-layouts');
    return saved ? JSON.parse(saved) : DEFAULT_LAYOUTS;
  }, []);

  const [layouts, setLayouts] = useState(initialLayouts);

  const onLayoutChange = (currentLayout, allLayouts) => {
    setLayouts(allLayouts);
    localStorage.setItem('dashboard-layouts', JSON.stringify(allLayouts));
  };

  const resetLayout = () => {
    if (window.confirm('Reset dashboard layout to default?')) {
      setLayouts(DEFAULT_LAYOUTS);
      localStorage.removeItem('dashboard-layouts');
    }
  };

  const cardClass = "h-full w-full";

  return (
    <div className="space-y-6 pb-20">
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
          <p className="text-sm text-[--text-muted] mt-1">Customizable real-time signal monitoring.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={resetLayout}
            className="p-2 rounded-lg border border-white/5 text-[--text-muted] hover:text-white hover:bg-white/5 transition-all cursor-pointer"
            title="Reset Layout"
          >
            <RotateCcw size={18} />
          </button>
          
          <button 
            onClick={() => setShowTradeForm({})}
            className="px-4 py-2 rounded-lg bg-green-500/10 text-green-400 border border-green-500/20 text-sm font-medium hover:bg-green-500/20 transition-all flex items-center gap-2 cursor-pointer"
          >
            <Activity size={16} />
            Log Live Trade
          </button>
        </div>
      </div>

      {/* Main Draggable Grid */}
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={30}
        draggableHandle=".cursor-grab"
        onLayoutChange={onLayoutChange}
        margin={[24, 24]}
      >
        <div key="kpi">
          <StrategyBreakdown />
        </div>

        <div key="near">
          <NearTrigger className={cardClass} onSymbolClick={openAsset} />
        </div>

        <div key="signals">
          <SignalsPanel className={cardClass} onSymbolClick={openAsset} />
        </div>

        <div key="open-pos">
          <OpenPositions 
            onLogReal={(prefill) => setShowTradeForm(prefill || true)} 
            onSymbolClick={openAsset}
            className={cardClass} 
          />
        </div>

        <div key="equity">
          <EquityCurve className={cardClass} />
        </div>

        <div key="trades">
          <ClosedTrades onSymbolClick={openAsset} className={cardClass} />
        </div>

        <div key="live-pos">
          <LivePositions onSymbolClick={openAsset} className={cardClass} />
        </div>

        <div key="market">
          <MarketOverview onSymbolClick={openAsset} className={cardClass} />
        </div>

        <div key="comparison">
          <PaperVsLive className={cardClass} />
        </div>
      </ResponsiveGridLayout>

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
