import { useState, useMemo } from 'react';
import { useApi } from '../hooks/useApi';
import { useRefresh } from '../hooks/useRefresh';
import { api } from '../api/client';
import { formatDate } from '../utils/format';
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
  });
  const [limit] = useState(50);

  const params = useMemo(() => {
    const p = { limit };
    if (filters.strategy) p.strategy = filters.strategy;
    if (filters.symbol) p.symbol = filters.symbol;
    if (filters.source) p.source = filters.source;
    if (filters.search) p.search = filters.search;
    return p;
  }, [filters, limit]);

  const { data, loading, error } = useApi(
    () => api.journalEntries(params),
    [params, refreshKey]
  );

  // Group entries by entry_date
  const grouped = useMemo(() => {
    if (!data?.entries) return [];
    const groups = {};
    for (const entry of data.entries) {
      const date = entry.entry_date;
      if (!groups[date]) groups[date] = [];
      groups[date].push(entry);
    }
    return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]));
  }, [data]);

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
      {data?.entries && (
        <div className="animate-slide-up" style={{ animationDelay: '20ms' }}>
          <JournalCharts entries={data.entries} />
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

        {data && data.entries.length === 0 && (
          <div className="text-center text-[--text-muted] text-sm py-12">
            No trades found
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
            Showing {data.entries.length} of {data.total} trades
          </div>
        )}
      </div>
    </div>
  );
}
