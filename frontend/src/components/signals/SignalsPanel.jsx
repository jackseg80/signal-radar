import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import { groupBuySignals } from './groupBuySignals';

const labels = { rsi2: 'RSI(2)', ibs: 'IBS', tom: 'TOM' };
const scoreLabel = (value) => value == null ? 'historique insuffisant' :
  (Number(value) * 100).toLocaleString('fr-CH', { maximumFractionDigits: 2, signDisplay: 'always' }) + ' %/mois (score historique)';
const warning = (reasons = []) => reasons.some((reason) =>
  reason.includes('next-open validation') || reason.includes('Saxo fees') ||
  reason.includes('fewer than 30') || reason.includes('market data missing'));

export default function SignalsPanel({ className, onSymbolClick, onRecord }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.signalsToday(), [refreshKey]);
  const strategies = data?.strategies || {};
  const buys = groupBuySignals(strategies);
  const all = Object.entries(strategies).flatMap(([strategy, group]) =>
    (group.signals || []).map((signal) => ({ ...signal, strategy })));
  const exits = all.filter((signal) => ['SELL', 'SAFETY_EXIT'].includes(signal.technical_signal));
  const virtualExits = all.filter((signal) =>
    ['SELL', 'SAFETY_EXIT'].includes(signal.follow_signal) &&
    !['SELL', 'SAFETY_EXIT'].includes(signal.technical_signal));
  const missing = [...new Set(all.filter((signal) => signal.technical_signal === 'DATA_MISSING').map((signal) => signal.symbol))];

  if (loading) return <Card title="Radar · actions" className={className}><LoadingState rows={4} /></Card>;
  if (error) return <Card title="Radar · actions" className={className}><ErrorState message={error} onRetry={refetch} /></Card>;
  if (!data?.source_session) return <Card title="Radar · actions" className={className}><EmptyState message="Aucun scan disponible." /></Card>;

  return (
    <Card title="Radar · actions" subtitle="Les signaux sont des informations à examiner, pas des ordres ni une vérification de ton solde Saxo." className={className}>
      <div className="space-y-5 text-sm">
        <p className="text-[--text-secondary]">Clôture US {data.source_session} · ouverture visée {data.target_session} · {buys.length} action(s) avec signal d’achat</p>
        {missing.length > 0 && <p className="rounded bg-amber-500/10 p-3 text-amber-300">Cours manquants : {missing.join(', ')}. Aucune conclusion sur ces actions pour cette séance.</p>}
        <section className="space-y-3">
          <h3 className="font-semibold text-white">Signaux d’achat · toutes les actions</h3>
          {buys.length === 0 && <p className="text-[--text-muted]">Aucun déclenchement technique sur cette séance.</p>}
          {buys.map(({ symbol, rows }) => (
            <article key={symbol} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button type="button" onClick={() => onSymbolClick?.(symbol)} className="text-lg font-bold text-white hover:text-green-300">{symbol}</button>
                {rows.length > 1 && <span className="rounded bg-blue-500/10 px-2 py-1 text-xs text-blue-300">{rows.length} stratégies · même séance</span>}
              </div>
              <div className="mt-3 space-y-2">
                {rows.map((row) => (
                  <div key={row.strategy} className="flex flex-wrap items-center justify-between gap-2 rounded border border-white/5 p-2">
                    <div><strong className="text-white">{labels[row.strategy] || row.strategy}</strong><span className="ml-2 text-xs text-[--text-secondary]">{scoreLabel(row.score)}</span>
                      {warning(row.reasons) && <p className="text-xs text-amber-300">Validation récente ou frais réels à vérifier avant décision.</p>}
                    </div>
                    <button type="button" onClick={() => onRecord?.({
                      symbol, strategy: row.strategy, signal_session: row.source_session || data.source_session,
                    })} className="rounded border border-green-500/30 px-2 py-1 text-xs text-green-300">Saisir mon achat</button>
                  </div>
                ))}
              </div>
              {rows.length > 1 && <p className="mt-2 text-xs text-[--text-muted]">La coïncidence des signaux n’a pas de gain de probabilité chiffré démontré.</p>}
            </article>
          ))}
        </section>
        <section className="space-y-2 border-t border-white/10 pt-4">
          <h3 className="font-semibold text-white">Sorties par stratégie</h3>
          {exits.length === 0 && virtualExits.length === 0 && <p className="text-[--text-muted]">Aucune sortie signalée sur cette séance.</p>}
          {exits.map((signal) => <p key={signal.symbol + signal.strategy} className="rounded bg-amber-500/10 p-2 text-amber-300">{signal.symbol} · {labels[signal.strategy]} · sortie de la stratégie à examiner ; aucune clôture automatique.</p>)}
          {virtualExits.map((signal) => <p key={signal.symbol + signal.strategy + 'virtual'} className="rounded bg-blue-500/10 p-2 text-blue-300">{signal.symbol} · {labels[signal.strategy]} · sortie du suivi virtuel indépendant.</p>)}
        </section>
      </div>
    </Card>
  );
}
