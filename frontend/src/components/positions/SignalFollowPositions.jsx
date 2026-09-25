import React from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import { formatPrice, formatPnl, pnlColor } from '../../utils/format';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';

export default function SignalFollowPositions({ onSymbolClick }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(
    () => api.signalFollowPositions(), [refreshKey],
  );
  return (
    <Card
      title="Positions ouvertes · suivi des signaux"
      subtitle="Chaque stratégie au score positif est suivie séparément, avec 5 000 USD virtuels par signal. Aucun lien avec Saxo ni avec le portefeuille papier commun."
    >
      {loading && <LoadingState rows={3} />}
      {error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && data && (
        <div className="space-y-3 text-xs">
          {!data.costs_verified && (
            <p className="text-amber-300">Résultats provisoires : frais et exécution Saxo encore à vérifier.</p>
          )}
          {data.pending_orders.length > 0 && (
            <div className="rounded border border-blue-500/20 bg-blue-500/5 p-2 text-blue-300">
              À la prochaine ouverture : {data.pending_orders.map((order) =>
                `${order.symbol} · ${order.strategy.toUpperCase()} · ${order.side === 'BUY' ? 'entrée' : 'sortie'} ${order.target_session}`
              ).join(' ; ')}
            </div>
          )}
          {data.positions.length === 0
            ? <p className="text-[--text-muted]">Aucune position virtuelle ouverte. Les signaux en attente apparaissent ci-dessus.</p>
            : <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="border-b border-white/10 text-[--text-muted] uppercase">
                    <tr><th className="p-2">Titre</th><th className="p-2">Stratégie</th><th className="p-2">Entrée</th><th className="p-2 text-right">Actions</th><th className="p-2 text-right">Ouverture $</th><th className="p-2 text-right">Dernier $</th><th className="p-2 text-right">P/L estimé</th></tr>
                  </thead>
                  <tbody>
                    {data.positions.map((position) => (
                      <tr key={position.id} className="border-b border-white/5">
                        <td className="p-2"><button type="button" className="font-semibold text-white hover:text-green-400" onClick={() => onSymbolClick?.(position.symbol)}>{position.symbol}</button></td>
                        <td className="p-2 uppercase">{position.strategy}</td>
                        <td className="p-2">{position.entry_session}</td>
                        <td className="p-2 text-right">{position.shares}</td>
                        <td className="p-2 text-right">{formatPrice(position.entry_price)}</td>
                        <td className="p-2 text-right">{position.current_price == null ? '—' : formatPrice(position.current_price)}</td>
                        <td className={`p-2 text-right ${pnlColor(position.unrealized_pnl_estimate)}`}>
                          {position.unrealized_pnl_estimate == null ? '—' : formatPnl(position.unrealized_pnl_estimate)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>}
          <p className="text-[--text-muted]">Suivi démarré avec cette nouvelle série. {data.closed_count} position(s) virtuelles clôturées ; aucun cumul de capital entre signaux.</p>
        </div>
      )}
    </Card>
  );
}
