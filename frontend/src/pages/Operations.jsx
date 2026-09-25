import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useApi } from '../hooks/useApi';
import { useRefresh } from '../hooks/useRefresh.jsx';
import LiveTradeForm from '../components/live/LiveTradeForm';

const money = (value) => value == null ? '—' : Number(value).toLocaleString('fr-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' USD';
const typeLabel = (value) => value === 'stock' ? 'Action' : value === 'cfd' ? 'CFD sur action' : 'À préciser';

export default function Operations() {
  const { refreshKey, refresh } = useRefresh();
  const [query, setQuery] = useSearchParams();
  const [form, setForm] = useState(query.has('symbol') ? {
    symbol: query.get('symbol'), strategy: query.get('strategy'),
    signal_session: query.get('signal_session'),
  } : null);
  const [closeTrade, setCloseTrade] = useState(null);
  const [cashInput, setCashInput] = useState('');
  const [cashError, setCashError] = useState('');
  const [savingCash, setSavingCash] = useState(false);
  const [tradeError, setTradeError] = useState('');
  const { data: cashData } = useApi(() => api.manualCash(), [refreshKey]);
  const { data: openData, error: openError } = useApi(() => api.liveActive(), [refreshKey]);
  const { data: closedData, error: closedError } = useApi(() => api.liveClosed({ limit: 1000 }), [refreshKey]);
  const { data: signalsData } = useApi(() => api.signalsToday(), [refreshKey]);
  const snapshot = cashData?.snapshot;
  const open = openData?.trades || [];
  const closed = closedData?.trades || [];
  const activeSignals = Object.entries(signalsData?.strategies || {}).flatMap(([strategy, group]) =>
    group.signals.map((signal) => ({ ...signal, strategy }))
  );
  const saveCash = async (event) => {
    event.preventDefault();
    setSavingCash(true);
    setCashError('');
    try {
      await api.saveManualCash({ available_usd: Number(cashInput) });
      setCashInput('');
      refresh();
    } catch (failure) {
      setCashError(failure.message);
    } finally {
      setSavingCash(false);
    }
  };
  const finish = () => {
    setForm(null);
    setCloseTrade(null);
    setQuery({});
    refresh();
  };
  const remove = async (trade) => {
    if (!window.confirm('Supprimer cette saisie ' + trade.symbol + ' ? Cette correction ne modifie rien chez Saxo.')) return;
    setTradeError('');
    try {
      await api.liveDelete(trade.id);
      refresh();
    } catch (failure) {
      setTradeError(failure.message);
    }
  };
  const row = (trade, isOpen) => {
    const exit = activeSignals.find((signal) => signal.symbol === trade.symbol &&
      signal.strategy === trade.strategy &&
      ['SELL', 'SAFETY_EXIT'].includes(signal.technical_signal));
    const days = Math.floor((Date.now() - new Date(trade.entry_date + 'T12:00:00').getTime()) / 86400000);
    return (
      <article key={trade.id} className="glass-card rounded-xl border border-white/10 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div><strong className="text-white">{trade.symbol}</strong> <span className="text-xs text-[--text-secondary]">{typeLabel(trade.instrument_type)} · {trade.strategy.toUpperCase()} principale</span></div>
          <span className="text-xs text-[--text-muted]">{trade.entry_date} · {trade.shares} unité(s) à {money(trade.entry_price)}</span>
        </div>
        <p className="mt-2 text-xs text-[--text-secondary]">
          {trade.signal_session ? 'Signal du ' + trade.signal_session + (trade.signal_linked ? ' · retrouvé dans le scan' : ' · référence manuelle') : 'Signal exact non renseigné'}
        </p>
        {trade.other_buy_strategies?.length > 0 && <p className="mt-1 text-xs text-blue-300">Autres signaux le même jour : {trade.other_buy_strategies.map((value) => value.toUpperCase()).join(', ')} · leurs sorties restent indépendantes.</p>}
        {isOpen ? (
          <>
            {exit && <p className="mt-2 rounded bg-amber-500/10 p-2 text-sm text-amber-300">Sortie {trade.strategy.toUpperCase()} à examiner · séance {signalsData.source_session}. Aucun ordre automatique.</p>}
            {days > 14 && <p className="mt-2 text-xs text-amber-300">Position ouverte depuis plus de 14 jours : revoir la durée prévue.</p>}
            <button type="button" onClick={() => setCloseTrade(trade)} className="mt-3 rounded-lg border border-green-500/30 px-3 py-1.5 text-sm text-green-300">Saisir la clôture</button>
          </>
        ) : (
          <>
            <p className="mt-2 text-xs text-[--text-secondary]">Clôture {trade.exit_date} à {money(trade.exit_price)}
              {trade.instrument_type === 'cfd' && <span> · financement {trade.financing_known ? money(trade.financing_cost) : 'à préciser'}</span>}
            </p>
            <p className={'mt-1 text-sm ' + (trade.pnl_dollars >= 0 ? 'text-green-300' : 'text-red-300')}>
              {trade.net_pnl_verified ? 'Résultat net' : 'Résultat provisoire'} : {money(trade.pnl_dollars)}
              {!trade.net_pnl_verified && <span className="ml-2 text-xs text-amber-300">Coûts ou instrument à préciser</span>}
            </p>
          </>
        )}
        <button type="button" onClick={() => remove(trade)} className="mt-3 text-xs text-[--text-muted] hover:text-red-300">Supprimer une saisie erronée</button>
      </article>
    );
  };

  return (
    <div className="space-y-6 pb-16">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Mes opérations Signal Radar</h1>
          <p className="text-sm text-[--text-muted]">Uniquement les achats que tu décides de saisir. Ce journal ne représente pas tout ton portefeuille Saxo.</p>
        </div>
        <button type="button" onClick={() => setForm({})} className="rounded-lg bg-green-500/20 px-4 py-2 font-semibold text-green-300">Saisir un achat</button>
      </header>
      <section className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4">
        <h2 className="font-semibold text-white">Liquidités Saxo · saisie manuelle</h2>
        <p className="text-xs text-[--text-muted]">Photographie déclarée, indépendante de ce journal partiel. Elle ne calcule ni marge CFD, ni capacité d’achat, ni valeur totale du compte.</p>
        <p className="mt-2 text-sm text-blue-200">{snapshot ? money(snapshot.available_usd) + ' · renseigné le ' + new Date(snapshot.recorded_at).toLocaleString('fr-CH') : 'Aucune valeur renseignée'}</p>
        <form onSubmit={saveCash} className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-xs text-[--text-secondary]">Liquidités disponibles USD<input required type="number" min="0" step="0.01" value={cashInput} onChange={(e) => setCashInput(e.target.value)} className="mt-1 block rounded border border-white/10 bg-black/30 p-2 text-white" /></label>
          <button disabled={savingCash} className="rounded bg-blue-500/20 px-4 py-2 text-sm text-blue-200">Enregistrer la valeur</button>
        </form>
        {cashError && <p role="alert" className="mt-2 text-xs text-red-400">{cashError}</p>}
      </section>
      {(tradeError || openError || closedError) && <p role="alert" className="text-red-400">{tradeError || openError || closedError}</p>}
      <section className="space-y-3"><h2 className="text-lg font-semibold text-white">Positions ouvertes · {open.length}</h2>{open.length ? open.map((trade) => row(trade, true)) : <p className="text-sm text-[--text-muted]">Aucune opération saisie comme ouverte.</p>}</section>
      <section className="space-y-3"><h2 className="text-lg font-semibold text-white">Opérations clôturées · {closed.length}</h2>{closed.length ? closed.map((trade) => row(trade, false)) : <p className="text-sm text-[--text-muted]">Aucune opération clôturée.</p>}</section>
      {form && <LiveTradeForm prefill={form} onDone={finish} onCancel={() => { setForm(null); setQuery({}); }} />}
      {closeTrade && <LiveTradeForm mode="close" prefill={closeTrade} onDone={finish} onCancel={() => setCloseTrade(null)} />}
    </div>
  );
}
