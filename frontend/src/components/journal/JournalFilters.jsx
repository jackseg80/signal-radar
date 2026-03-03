import { useState, useEffect } from 'react';
import { STRATEGY_LABELS } from '../../utils/format';

const STRATEGIES = [
  { value: '', label: 'All strategies' },
  { value: 'rsi2', label: STRATEGY_LABELS.rsi2 },
  { value: 'ibs', label: STRATEGY_LABELS.ibs },
  { value: 'tom', label: STRATEGY_LABELS.tom },
];

const SOURCES = [
  { value: '', label: 'All sources' },
  { value: 'paper', label: 'Paper' },
  { value: 'live', label: 'Live' },
];

const selectClass =
  'bg-[--bg-primary] border border-[--border-subtle] rounded px-3 py-1.5 text-sm text-[--text-primary] focus:border-blue-500/50 focus:outline-none cursor-pointer';

const inputClass =
  'bg-[--bg-primary] border border-[--border-subtle] rounded px-3 py-1.5 text-sm text-[--text-primary] focus:border-blue-500/50 focus:outline-none';

export default function JournalFilters({ filters, onChange }) {
  const [searchInput, setSearchInput] = useState(filters.search || '');

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== (filters.search || '')) {
        onChange({ ...filters, search: searchInput || null });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const update = (key, value) => {
    onChange({ ...filters, [key]: value || null });
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <select
        value={filters.strategy || ''}
        onChange={(e) => update('strategy', e.target.value)}
        className={selectClass}
      >
        {STRATEGIES.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>

      <input
        type="text"
        value={filters.symbol || ''}
        onChange={(e) => update('symbol', e.target.value.toUpperCase())}
        placeholder="Symbol"
        className={`${inputClass} w-24`}
      />

      <select
        value={filters.source || ''}
        onChange={(e) => update('source', e.target.value)}
        className={selectClass}
      >
        {SOURCES.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>

      <input
        type="text"
        value={searchInput}
        onChange={(e) => setSearchInput(e.target.value)}
        placeholder="Search notes..."
        className={`${inputClass} w-40`}
      />
    </div>
  );
}
