import React from 'react';
import { Search, Filter, X } from 'lucide-react';

export default function JournalFilters({ filters, onChange }) {
  const strategies = ['rsi2', 'ibs', 'tom'];
  const sources = [
    { value: 'paper', label: 'Paper Trading' },
    { value: 'live', label: 'Live Trades' }
  ];
  const assetTypes = [
    { value: 'Stock', label: 'Stocks' },
    { value: 'ETF', label: 'ETFs' },
    { value: 'Forex', label: 'Forex' }
  ];

  const clearFilters = () => {
    onChange({
      strategy: null,
      symbol: null,
      source: null,
      search: null,
      assetType: null
    });
  };

  const hasActiveFilters = Object.values(filters).some(v => v !== null && v !== '');

  const selectClass = "bg-[#1a1d27] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-green-500/50 cursor-pointer appearance-none min-w-[130px]";

  return (
    <div className="flex flex-wrap gap-4 p-4 bg-white/[0.02] border border-white/5 rounded-xl items-center shadow-lg">
      <div className="flex items-center gap-2 mr-2">
        <Filter size={14} className="text-[--text-muted]" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-[--text-muted]">Filtrer Journal :</span>
      </div>

      <select
        value={filters.strategy || ''}
        onChange={(e) => onChange({ ...filters, strategy: e.target.value || null })}
        className={selectClass}
      >
        <option value="">Toutes Stratégies</option>
        {strategies.map(s => <option key={s} value={s}>{s.toUpperCase()}</option>)}
      </select>

      <select
        value={filters.source || ''}
        onChange={(e) => onChange({ ...filters, source: e.target.value || null })}
        className={selectClass}
      >
        <option value="">Tous Comptes</option>
        {sources.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>

      <select
        value={filters.assetType || ''}
        onChange={(e) => onChange({ ...filters, assetType: e.target.value || null })}
        className={selectClass}
      >
        <option value="">Tous Types</option>
        {assetTypes.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
      </select>

      <div className="relative flex-1 min-w-[200px]">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[--text-muted]" />
        <input
          type="text"
          value={filters.search || ''}
          onChange={(e) => onChange({ ...filters, search: e.target.value || null })}
          placeholder="Rechercher symbole ou note..."
          className="w-full bg-[#1a1d27] border border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white outline-none focus:border-green-500/50"
        />
      </div>

      {hasActiveFilters && (
        <button
          onClick={clearFilters}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 text-[--text-muted] hover:text-white transition-all text-xs cursor-pointer"
        >
          <X size={14} />
          Reset
        </button>
      )}
    </div>
  );
}
