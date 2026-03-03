import { useState, useEffect, useCallback, useRef } from 'react';
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
  
  // Dashboard columns resizing logic
  const [splitRatio, setSplitRatio] = useState(
    parseFloat(localStorage.getItem('dashboard-split')) || 40
  );
  const isResizing = useRef(false);
  const containerRef = useRef(null);

  const startResizing = useCallback((e) => {
    e.preventDefault();
    isResizing.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    
    const overlay = document.createElement('div');
    overlay.id = 'dashboard-resize-overlay';
    overlay.style.position = 'fixed';
    overlay.style.inset = '0';
    overlay.style.zIndex = '9999';
    overlay.style.cursor = 'col-resize';
    document.body.appendChild(overlay);
  }, []);

  const stopResizing = useCallback(() => {
    if (!isResizing.current) return;
    isResizing.current = false;
    document.body.style.cursor = 'default';
    document.body.style.userSelect = 'auto';
    const overlay = document.getElementById('dashboard-resize-overlay');
    if (overlay) overlay.remove();
    localStorage.setItem('dashboard-split', splitRatio);
  }, [splitRatio]);

  const resize = useCallback((e) => {
    if (isResizing.current && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const offset = e.clientX - rect.left;
      const percentage = (offset / rect.width) * 100;
      // Constraints: min 20%, max 70%
      const newRatio = Math.min(Math.max(20, percentage), 70);
      setSplitRatio(newRatio);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', resize);
    window.addEventListener('mouseup', stopResizing);
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [resize, stopResizing]);

  // Consistent styling for cards in this layout
  const cardClass = "h-auto overflow-hidden flex flex-col animate-slide-up transition-all duration-300";
  const tallCardClass = "h-auto max-h-[850px] overflow-hidden flex flex-col animate-slide-up transition-all duration-300";

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

      {/* 2. Main Layout - Resizable 2-Column Grid */}
      <div 
        ref={containerRef}
        className="flex flex-col lg:flex-row gap-0 items-start min-h-[600px]"
      >
        {/* LEFT COLUMN: Intelligence & Signals */}
        <div 
          style={{ width: `${splitRatio}%` }} 
          className="space-y-6 w-full lg:w-auto shrink-0 pr-0 lg:pr-3"
        >
           <NearTrigger className={cardClass} />
           <SignalsPanel className={tallCardClass} />
        </div>

        {/* Resizer Handle (Hidden on mobile) */}
        <div
          onMouseDown={startResizing}
          className="hidden lg:flex w-2 self-stretch hover:bg-green-500/10 cursor-col-resize items-center justify-center group z-10"
        >
          <div className="w-[1px] h-24 bg-white/5 group-hover:bg-green-500/40 transition-colors" />
        </div>

        {/* RIGHT COLUMN: Portfolio & Execution */}
        <div 
          style={{ width: `${100 - splitRatio}%` }}
          className="flex-1 space-y-6 w-full lg:w-auto pl-0 lg:pl-3 mt-6 lg:mt-0"
        >
           <OpenPositions 
             onLogReal={(prefill) => setShowTradeForm(prefill || true)} 
             className={cardClass} 
           />
           
           <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <EquityCurve className={cardClass} />
              <ClosedTrades className={cardClass} />
           </div>

           <LivePositions className={cardClass} />
        </div>
      </div>

      {/* 3. Market Overview (Full Width - Bottom) */}
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
