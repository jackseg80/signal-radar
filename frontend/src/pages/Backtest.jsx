import { useState } from 'react';
import CompareMatrix from '../components/backtest/CompareMatrix';
import ValidationsTable from '../components/backtest/ValidationsTable';

const TABS = [
  { key: 'compare', label: 'Matrice de Confiance' },
  { key: 'explorer', label: 'Explorateur de Backtests' },
];

export default function Backtest() {
  const [activeTab, setActiveTab] = useState('compare');

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-white/5 pb-4">
        <div>
          <h1 
            className="text-2xl font-bold text-white tracking-tight flex items-center gap-3"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}
          >
            Analyse Quantitative
          </h1>
          <p className="text-sm text-[--text-muted] mt-1">Validation de la robustesse et performance historique des stratégies.</p>
        </div>
      </div>

      {/* Sub-tabs - Sticky at top-16 (Navbar is h-16) */}
      <div className="sticky top-16 z-40 bg-[--bg-primary]/80 backdrop-blur-md py-4 border-b border-transparent">
        <div className="flex gap-1 animate-fade-in bg-white/[0.02] p-1 rounded-xl w-fit border border-white/5 shadow-xl">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-6 py-2 rounded-lg text-sm transition-all duration-300 cursor-pointer ${
                activeTab === tab.key
                  ? 'bg-green-500/10 text-green-400 font-bold shadow-[0_0_15px_rgba(34,197,94,0.1)]'
                  : 'text-[--text-muted] hover:text-[--text-secondary] hover:bg-white/5'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="animate-slide-up">
        {activeTab === 'compare' && <CompareMatrix />}
        {activeTab === 'explorer' && <ValidationsTable />}
      </div>
    </div>
  );
}
