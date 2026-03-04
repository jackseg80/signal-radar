import { useState, useMemo } from 'react';
import { useApi } from '../hooks/useApi';
import { useRefresh } from '../hooks/useRefresh';
import { api } from '../api/client';
import { formatDate, getAssetType } from '../utils/format';
import JournalFilters from '../components/journal/JournalFilters';
import JournalStats from '../components/journal/JournalStats';
import JournalCharts from '../components/journal/JournalCharts';
import TradeCard from '../components/journal/TradeCard';

export default function Journal() {
  const { refreshKey, refresh } = useRefresh();
  const [filters, setFilters] = useState({
    strategy: null,
    symbol: null,
    source: null,
    search: null,
    assetType: null
  });
  const [limit] = useState(100); // Increased limit to allow client-side type filtering

  const params = useMemo(() => {
    const p = { limit };
    if (filters.strategy) p.strategy = filters.strategy;
    if (filters.symbol) p.symbol = filters.symbol;
    if (filters.source) p.source = filters.source;
    if (filters.search) p.search = filters.search;
    return p;
  }, [filters.strategy, filters.symbol, filters.source, filters.search, limit]);

  const { data, loading, error } = useApi(
    () => api.journalEntries(params),
    [params, refreshKey]
  );

  // Group entries by entry_date AND apply client-side Asset Type filter
  const filteredEntries = useMemo(() => {
    if (!data?.entries) return [];
    let entries = data.entries;
    
    if (filters.assetType) {
      entries = entries.filter(e => getAssetType(e.symbol).label.toUpperCase() === filters.assetType.toUpperCase());
    }
    
    return entries;
  }, [data, filters.assetType]);

  const grouped = useMemo(() => {
    const groups = {};
    for (const entry of filteredEntries) {
      const date = entry.entry_date;
      if (!groups[date]) groups[date] = [];
      groups[date].push(entry);
    }
    return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]));
  }, [filteredEntries]);

  return (
    <div className="space-y-6">
      {/* Header + Stats */}
      <div className="animate-slide-up" style={{ animationDelay: '0ms' }}>
        <h2
          className="text-lg font-semibold text-[--text-primary] mb-3"
          style={{ fontFamily: "'Space Grotesk', sans-serif" }}
        >
          Trade Journal
        </h2>
        <JournalStats stats={data?.stats} />
      </div>

      {/* Analytics Charts */}
      {filteredEntries.length > 0 && (
        <div className="animate-slide-up" style={{ animationDelay: '20ms' }}>
          <JournalCharts entries={filteredEntries} />
        </div>
      )}

      {/* Filters */}
      <div className="animate-slide-up" style={{ animationDelay: '40ms' }}>
        <JournalFilters filters={filters} onChange={setFilters} />
      </div>

      {/* Timeline */}
      <div className="animate-slide-up" style={{ animationDelay: '80ms' }}>
        {loading && !data && (
          <div className="text-center text-[--text-muted] text-sm py-12">Loading...</div>
        )}

        {error && (
          <div className="text-center text-red-400 text-sm py-12">{error}</div>
        )}

        {data && filteredEntries.length === 0 && (
          <div className="text-center text-[--text-muted] text-sm py-12">
            No trades found matching filters
          </div>
        )}

        {grouped.map(([date, entries]) => (
          <div key={date} className="mb-6">
            <div className="text-xs text-[--text-muted] uppercase tracking-wider mb-2 sticky top-0 bg-[--bg-primary] py-1 z-10">
              {formatDate(date)}
            </div>
            <div className="space-y-2">
              {entries.map((entry) => (
                <TradeCard
                  key={`${entry.source}-${entry.id}`}
                  entry={entry}
                  onSaved={refresh}
                />
              ))}
            </div>
          </div>
        ))}

        {data && data.total > data.entries.length && (
          <div className="text-center text-xs text-[--text-muted] py-4">
            Showing {filteredEntries.length} of {data.total} trades
          </div>
        )}
      </div>
    </div>
  );
}
