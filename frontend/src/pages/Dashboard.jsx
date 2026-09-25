import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Responsive, WidthProvider } from 'react-grid-layout/legacy';
import { RotateCcw } from 'lucide-react';
import SignalsPanel from '../components/signals/SignalsPanel';
import NearTrigger from '../components/signals/NearTrigger';
import MarketOverview from '../components/market/MarketOverview';
import PaperSnapshot from '../components/positions/PaperSnapshot';
import ObservationPanel from '../components/account/ObservationPanel';
import { useAssetView } from '../hooks/useAssetView.jsx';

const ResponsiveGridLayout = WidthProvider(Responsive);
const LAYOUT_KEY = 'radar-layout-v1';
const DEFAULT_LAYOUTS = {
  lg: [
    { i: 'signals', x: 0, y: 0, w: 5, h: 18, minW: 3, minH: 7 },
    { i: 'market', x: 5, y: 0, w: 7, h: 18, minW: 4, minH: 7 },
    { i: 'near', x: 0, y: 18, w: 4, h: 10, minW: 3, minH: 5 },
    { i: 'paper', x: 4, y: 18, w: 4, h: 7, minW: 3, minH: 5 },
  ],
  md: [
    { i: 'signals', x: 0, y: 0, w: 5, h: 18, minW: 3, minH: 7 },
    { i: 'market', x: 5, y: 0, w: 5, h: 18, minW: 4, minH: 7 },
    { i: 'near', x: 0, y: 18, w: 5, h: 10, minW: 3, minH: 5 },
    { i: 'paper', x: 5, y: 18, w: 5, h: 7, minW: 3, minH: 5 },
  ],
  sm: [
    { i: 'signals', x: 0, y: 0, w: 6, h: 16, minW: 3, minH: 7 },
    { i: 'market', x: 0, y: 16, w: 6, h: 16, minW: 4, minH: 7 },
    { i: 'near', x: 0, y: 32, w: 3, h: 10, minW: 3, minH: 5 },
    { i: 'paper', x: 3, y: 32, w: 3, h: 7, minW: 3, minH: 5 },
  ],
  xs: [
    { i: 'signals', x: 0, y: 0, w: 4, h: 15, minW: 3, minH: 7 },
    { i: 'market', x: 0, y: 15, w: 4, h: 14, minW: 4, minH: 7 },
    { i: 'near', x: 0, y: 29, w: 4, h: 9, minW: 3, minH: 5 },
    { i: 'paper', x: 0, y: 38, w: 4, h: 9, minW: 3, minH: 5 },
  ],
  xxs: [
    { i: 'signals', x: 0, y: 0, w: 2, h: 15, minW: 2, minH: 7 },
    { i: 'market', x: 0, y: 15, w: 2, h: 14, minW: 2, minH: 7 },
    { i: 'near', x: 0, y: 29, w: 2, h: 9, minW: 2, minH: 5 },
    { i: 'paper', x: 0, y: 38, w: 2, h: 9, minW: 2, minH: 5 },
  ],
};

function loadLayouts() {
  try {
    const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY));
    return saved && Array.isArray(saved.lg) ? { ...DEFAULT_LAYOUTS, ...saved } : DEFAULT_LAYOUTS;
  } catch {
    return DEFAULT_LAYOUTS;
  }
}

export default function Dashboard() {
  const { openAsset } = useAssetView();
  const navigate = useNavigate();
  const [layouts, setLayouts] = useState(loadLayouts);

  const record = ({ symbol, strategy, signal_session }) => {
    const params = new URLSearchParams({ symbol, strategy, signal_session });
    navigate('/operations?' + params.toString());
  };

  const saveLayouts = (_current, all) => {
    setLayouts(all);
    localStorage.setItem(LAYOUT_KEY, JSON.stringify(all));
  };

  const resetLayouts = () => {
    setLayouts(DEFAULT_LAYOUTS);
    localStorage.removeItem(LAYOUT_KEY);
  };

  return (
    <div className="space-y-5 pb-16">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Radar · actions</h1>
          <p className="text-sm text-[--text-muted]">Signaux techniques sur actions, indépendants du solde Saxo et de la simulation papier.</p>
        </div>
        <div className="flex items-center gap-3 text-xs text-[--text-muted]">
          <span className="hidden sm:inline">Glisse l’en-tête pour déplacer · coin inférieur droit pour redimensionner</span>
          <button type="button" onClick={resetLayouts} className="flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1.5 text-[--text-secondary] hover:text-white" title="Réinitialiser la disposition" aria-label="Réinitialiser la disposition du Radar">
            <RotateCcw size={14} /> Disposition
          </button>
        </div>
      </header>

      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={28}
        margin={[16, 16]}
        containerPadding={[0, 0]}
        draggableHandle=".cursor-grab"
        draggableCancel="button, a, input, select, textarea"
        onLayoutChange={saveLayouts}
      >
        <div key="signals" className="min-h-0"><SignalsPanel className="h-full" onSymbolClick={openAsset} onRecord={record} /></div>
        <div key="market" className="min-h-0"><MarketOverview className="h-full" onSymbolClick={openAsset} /></div>
        <div key="near" className="min-h-0"><NearTrigger className="h-full" onSymbolClick={openAsset} /></div>
        <div key="paper" className="min-h-0"><PaperSnapshot className="h-full" onSymbolClick={openAsset} /></div>
      </ResponsiveGridLayout>

      <details className="rounded-xl border border-blue-500/20 bg-blue-500/5">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-blue-200">Observation Saxo · 20 séances</summary>
        <div className="p-3 pt-0"><ObservationPanel /></div>
      </details>
    </div>
  );
}
