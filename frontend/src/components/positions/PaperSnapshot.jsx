import { Link } from 'react-router-dom';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPnl, pnlColor, STRATEGY_LABELS } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';

/** Compact paper positions for the configurable Radar grid. */
export default function PaperSnapshot({ className, onSymbolClick }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.openPositions(), [refreshKey]);
  const positions = data?.positions || [];

  return (
    <Card
      title="Simulation papier · positions ouvertes"
      subtitle="Suivi virtuel commun · sans effet sur les signaux"
      className={className}
      headerAction={<Link to="/paper" className="text-xs text-green-300 hover:text-green-200">Détails</Link>}
    >
      {loading && <LoadingState rows={2} />}
      {error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && (
        <div className="space-y-3 text-xs">
          <div className="flex items-center justify-between text-[--text-secondary]">
            <span>{positions.length} position{positions.length > 1 ? 's' : ''} ouverte{positions.length > 1 ? 's' : ''}</span>
            {positions.length > 0 && <span className={pnlColor(data?.total_unrealized_pnl)}>P/L indicatif {formatPnl(data?.total_unrealized_pnl)}</span>}
          </div>
          {positions.length === 0
            ? <p className="text-[--text-muted]">Aucune position papier ouverte.</p>
            : <div className="space-y-1.5">
                {positions.map((position) => (
                  <div key={position.id} className="flex items-center justify-between gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                    <div className="min-w-0">
                      <button type="button" onClick={() => onSymbolClick?.(position.symbol)} className="font-semibold text-white hover:text-green-300">{position.symbol}</button>
                      <span className="ml-2 text-[--text-muted]">{STRATEGY_LABELS[position.strategy] || position.strategy} · {position.shares} action{position.shares > 1 ? 's' : ''}</span>
                    </div>
                    <span className={`shrink-0 ${pnlColor(position.unrealized_pnl)}`}>{formatPnl(position.unrealized_pnl)}</span>
                  </div>
                ))}
              </div>}
        </div>
      )}
    </Card>
  );
}
