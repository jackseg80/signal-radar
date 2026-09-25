import { useEffect, useState } from 'react';
import { api } from '../../api/client';

function BrokerCheckForm({ item, onSaved }) {
  const [open, setOpen] = useState(item.saxo_open ?? '');
  const [execution, setExecution] = useState(item.execution_price ?? '');
  const [fees, setFees] = useState(item.actual_fees_usd ?? '');
  const [error, setError] = useState('');

  const save = async (event) => {
    event.preventDefault();
    try {
      await api.observationCheck({
        source_session: item.source_session,
        symbol: item.symbol,
        saxo_open: Number(open),
        execution_price: execution === '' ? null : Number(execution),
        actual_fees_usd: fees === '' ? null : Number(fees),
      });
      setError('');
      onSaved();
    } catch (failure) {
      setError(failure.message);
    }
  };

  return (
    <form onSubmit={save} className="grid grid-cols-1 gap-2 rounded border border-white/10 bg-black/20 p-2 text-xs md:grid-cols-5">
      <div className="font-bold text-white">{item.source_session} · {item.symbol}<div className="font-normal text-[--text-muted]">Ouverture {item.target_session}</div></div>
      <label>Ouverture Saxo USD<input className="mt-1 w-full rounded bg-black/40 p-1 text-white" type="number" min="0.01" step="0.0001" required value={open} onChange={(e) => setOpen(e.target.value)} /></label>
      <label>Exécution réelle USD<input className="mt-1 w-full rounded bg-black/40 p-1 text-white" type="number" min="0.01" step="0.0001" value={execution} onChange={(e) => setExecution(e.target.value)} /></label>
      <label>Frais réels USD<input className="mt-1 w-full rounded bg-black/40 p-1 text-white" type="number" min="0" step="0.01" value={fees} onChange={(e) => setFees(e.target.value)} /></label>
      <button type="submit" className="self-end rounded bg-blue-500/20 p-2 font-bold text-blue-300">Consigner</button>
      {error && <p className="text-red-400 md:col-span-5">{error}</p>}
      <p className="text-[--text-muted] md:col-span-5">
        Ouverture Yahoo simulée : {item.simulated_open == null ? 'en attente de la bougie' : `${item.simulated_open.toFixed(2)} USD`}
        {item.open_gap_pct != null ? ` · écart ouverture Saxo : ${item.open_gap_pct.toFixed(2)} %` : ''}
      </p>
    </form>
  );
}

export default function ObservationPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const reload = () => api.observationStatus().then(setData).catch((failure) => setError(failure.message));

  useEffect(() => { reload(); }, []);

  const start = async () => {
    try {
      await api.observationStart();
      reload();
    } catch (failure) {
      setError(failure.message);
    }
  };

  return (
    <section className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4" aria-label="Observation de 20 séances">
      <h2 className="text-sm font-bold text-white">Observation Saxo · 20 séances américaines</h2>
      <p className="mt-1 text-xs text-[--text-muted]">Comparez les ouvertures simulées aux cours Saxo et aux exécutions consignées. Cette période ne valide aucun titre automatiquement.</p>
      {data?.status === 'NOT_STARTED' ? (
        <button onClick={start} className="mt-3 rounded bg-blue-500/20 px-3 py-2 text-xs font-bold text-blue-300">Démarrer l’observation</button>
      ) : data && (
        <>
          <p className="mt-2 text-xs text-blue-200">{data.sessions_scanned}/{data.target_sessions} séances vérifiées · {data.candidate_count} candidature(s) · {data.missing_broker_checks} contrôle(s) Saxo manquant(s) · {data.status}</p>
          <div className="mt-3 max-h-80 space-y-2 overflow-y-auto">
            {(data.comparisons || []).map((item) => <BrokerCheckForm key={`${item.source_session}-${item.symbol}`} item={item} onSaved={reload} />)}
          </div>
        </>
      )}
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </section>
  );
}
