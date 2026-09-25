import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';

export default function PaperEquity() {
  const { refreshKey } = useRefresh();
  const { data, loading, error } = useApi(() => api.equityCurve(), [refreshKey]);
  const points = data?.data_points || [];
  return (
    <section className="glass-card rounded-xl p-4">
      <h2 className="mb-3 font-semibold text-white">Évolution du portefeuille papier</h2>
      {loading ? <p className="text-sm text-[--text-muted]">Chargement…</p> :
        error ? <p className="text-sm text-red-400">{error}</p> :
          points.length < 2 ? <p className="text-sm text-[--text-muted]">Pas encore assez de transactions papier clôturées.</p> :
            <div className="h-64" role="img" aria-label="Évolution du portefeuille papier en USD">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={points}>
                  <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip formatter={(value) => [Number(value).toFixed(2) + ' USD', 'Valeur papier']} />
                  <Area type="monotone" dataKey="equity" stroke="#22c55e" fill="#22c55e22" />
                </AreaChart>
              </ResponsiveContainer>
            </div>}
    </section>
  );
}
