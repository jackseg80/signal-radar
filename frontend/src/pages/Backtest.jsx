import { useState } from 'react';
import CompareMatrix from '../components/backtest/CompareMatrix';
import ValidationsTable from '../components/backtest/ValidationsTable';
import ScreensTable from '../components/backtest/ScreensTable';

const TABS = [
  { key: 'compare', label: 'Compare' },
  { key: 'validations', label: 'Validations' },
  { key: 'screens', label: 'Screens' },
];

export default function Backtest() {
  const [activeTab, setActiveTab] = useState('compare');

  return (
    <div className="space-y-6">
      {/* Sub-tabs */}
      <div className="flex gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm transition-colors cursor-pointer ${
              activeTab === tab.key
                ? 'bg-white/10 text-[--text-primary] font-medium'
                : 'text-[--text-muted] hover:text-[--text-secondary] hover:bg-white/5'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'compare' && <CompareMatrix />}
      {activeTab === 'validations' && <ValidationsTable />}
      {activeTab === 'screens' && <ScreensTable />}
    </div>
  );
}
