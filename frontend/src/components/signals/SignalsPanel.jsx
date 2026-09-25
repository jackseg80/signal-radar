import { useMemo } from 'react';
import { useApi } from '../../hooks/useApi';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { api } from '../../api/client';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import EmptyState from '../ui/EmptyState';
import StrategySection from './StrategySection';

function scoreText(score) {
  if (score == null || !Number.isFinite(Number(score))) return 'historique insuffisant';
  const percent = (Number(score) * 100).toLocaleString('fr-CH', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    signDisplay: 'always',
  });
  return percent + ' %/mois';
}

function reasonText(reason) {
  if (reason.startsWith('market data missing for:')) return 'Cours incomplets dans l’univers : ' + reason.split(': ')[1];
  if (reason.startsWith('combined with')) return 'Signal regroupé avec une autre stratégie sur ce titre';
  const known = {
    'Saxo cash and holdings not confirmed for this session': 'Compte Saxo non confirmé pour cette séance',
    'conservative net monthly return is not positive': 'Score prudent net non positif',
    'strategy has no current next-open validation': 'Stratégie non validée avec entrée à l’ouverture suivante',
    'next-open validation and Saxo fees not yet calibrated': 'Validation et frais Saxo encore provisoires',
    'next-open validation is older than 40 days': 'Validation de la stratégie à actualiser',
    'fewer than 30 completed historical trades': 'Moins de 30 transactions historiques',
    'single paper portfolio already committed': 'Portefeuille papier déjà engagé',
    'pending paper sale does not release budget': 'Vente papier en attente ; budget non libéré',
    'higher-ranked paper candidate has priority': 'Un autre candidat papier est mieux classé',
    'higher-ranked eligible candidate has priority': 'Un autre candidat réel est mieux classé',
    'paper portfolio cannot buy one share': 'Budget papier insuffisant pour une action',
    'confirmed Saxo cash cannot buy one share': 'Cash Saxo confirmé insuffisant pour une action',
    'title already held at Saxo': 'Titre déjà détenu chez Saxo',
    'one Signal Radar position already open': 'Une position Signal Radar est déjà ouverte',
    'target market open has passed': 'Ouverture visée déjà passée',
    'open journal trades disagree with confirmed holdings': 'Journal réel et titres Saxo confirmés divergents',
  };
  return known[reason] || reason;
}

function candidateRows(strategies) {
  const grouped = new Map();
  Object.entries(strategies).forEach(([strategy, group]) => {
    group.signals.forEach((signal) => {
      if (signal.technical_signal !== 'BUY' && signal.follow_signal !== 'BUY') return;
      const rows = grouped.get(signal.symbol) || [];
      rows.push({ ...signal, strategy });
      grouped.set(signal.symbol, rows);
    });
  });
  return [...grouped].map(([symbol, rows]) => {
    rows.sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));
    const primary = rows.find((row) => row.paper_status !== 'MERGED') || rows[0];
    return { symbol, rows, primary, score: rows[0].score };
  }).sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity) || a.symbol.localeCompare(b.symbol));
}

function paperLabel(row, score) {
  if (row.paper_status === 'PENDING_BUY') return 'Achat préparé pour la prochaine ouverture';
  if (row.paper_status === 'HOLD') return 'Position ouverte';
  if (score == null) return 'Pas d’achat : historique insuffisant';
  if (score <= 0) return 'Pas d’achat : score prudent non positif';
  if (row.paper_reasons?.some((reason) => reason.includes('portfolio already committed') || reason.includes('sale does not release budget'))) {
    return 'Pas d’achat : portefeuille déjà engagé';
  }
  return 'Pas d’achat papier';
}

function followLabel(rows) {
  const statuses = rows.map((row) => row.follow_status);
  if (statuses.includes('PENDING_BUY')) return 'Entrée virtuelle préparée pour la prochaine ouverture';
  if (statuses.includes('HOLD') || statuses.includes('PENDING_SELL')) return 'Position virtuelle déjà suivie';
  if (statuses.includes('EXPIRED')) return 'Signal expiré';
  if (statuses.includes('NOTIONAL_TOO_SMALL')) return 'Prix supérieur aux 5 000 USD virtuels';
  return 'Aucune entrée virtuelle préparée';
}

function Candidate({ candidate, onSymbolClick }) {
  const { symbol, rows, primary, score } = candidate;
  const positive = score != null && score > 0;
  const realPossible = rows.some((row) => row.signal === 'BUY' && row.eligibility === 'ELIGIBLE');
  const realReasons = [...new Set(rows.flatMap((row) => row.reasons || []))].filter((reason) => !reason.startsWith('combined with'));
  const paperReasons = [...new Set(rows.flatMap((row) => row.paper_reasons || []))].filter((reason) => !reason.startsWith('combined with'));
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="font-bold text-white hover:text-green-400" onClick={() => onSymbolClick?.(symbol)}>{symbol}</button>
        {rows.map((row) => (
          <span key={row.strategy} className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] uppercase text-[--text-secondary]">{row.strategy}</span>
        ))}
        <span className={positive ? 'ml-auto text-green-400' : 'ml-auto text-amber-400'}>
          Score prudent {scoreText(score)}
        </span>
      </div>
      <div className="mt-2 space-y-1 text-[--text-secondary]">
        {positive && <p className="text-blue-300">Suivi des signaux : {followLabel(rows)}</p>}
        <p>Portefeuille papier commun : {paperLabel(primary, score)}</p>
        <p className={realPossible ? 'text-green-400' : 'text-amber-400'}>
          Réel : {realPossible ? 'achat possible sous vérification manuelle' : 'aucun achat recommandé'}
        </p>
      </div>
      {(realReasons.length > 0 || paperReasons.length > 0) && (
        <details className="mt-2 border-t border-white/5 pt-2 text-[--text-muted]">
          <summary className="cursor-pointer">Voir les raisons</summary>
          {paperReasons.length > 0 && <p className="mt-2"><strong>Papier :</strong> {paperReasons.map(reasonText).join(' ; ')}</p>}
          {realReasons.length > 0 && <p className="mt-1"><strong>Réel :</strong> {realReasons.map(reasonText).join(' ; ')}</p>}
        </details>
      )}
    </div>
  );
}

export default function SignalsPanel({ className, onSymbolClick }) {
  const { refreshKey } = useRefresh();
  const { data, loading, error, refetch } = useApi(() => api.signalsToday(), [refreshKey]);
  const strategies = data?.strategies || {};
  const candidates = useMemo(() => candidateRows(strategies), [strategies]);
  if (loading) return <Card title="Signaux · prochaine ouverture" className={className}><LoadingState rows={4} /></Card>;
  if (error) return <Card title="Signaux · prochaine ouverture" className={className}><ErrorState message={error} onRetry={refetch} /></Card>;
  if (Object.keys(strategies).length === 0) return <Card title="Signaux · prochaine ouverture" className={className}><EmptyState message="Aucun scan disponible." /></Card>;

  const positive = candidates.filter((candidate) => candidate.score != null && candidate.score > 0);
  const other = candidates.filter((candidate) => candidate.score == null || candidate.score <= 0);
  const allSignals = Object.values(strategies).flatMap((group) => group.signals);
  const missing = [...new Map(allSignals.filter((signal) => signal.eligibility === 'DATA_MISSING').map((signal) => [signal.symbol, signal])).values()].sort((a, b) => a.symbol.localeCompare(b.symbol));
  const activeSymbols = new Set(allSignals.map((signal) => signal.symbol));
  const repairs = (data.verified_price_repairs || []).filter((repair) => activeSymbols.has(repair.symbol));
  const paperActions = [...new Map(allSignals.filter((signal) => ['PENDING_BUY', 'PENDING_SELL'].includes(signal.paper_status)).map((signal) => [signal.symbol + signal.paper_status, signal])).values()];
  const realCount = new Set(allSignals.filter((signal) => signal.signal === 'BUY' && signal.eligibility === 'ELIGIBLE').map((signal) => signal.symbol)).size;

  return (
    <Card title="Signaux · prochaine ouverture" subtitle="Un signal technique n’est pas une position ouverte." className={className}>
      <div className="space-y-4 text-xs">
        <div className="text-[--text-secondary]">
          <strong>Clôture {data.source_session}</strong> → ouverture {data.target_session}
          <div className={realCount > 0 ? 'text-green-400' : 'text-amber-400'}>
            {realCount > 0 ? realCount + ' achat(s) réel(s) possibles' : 'Aucun achat réel recommandé'}
          </div>
        </div>

        {paperActions.length > 0 && (
          <div className="rounded border border-blue-500/20 bg-blue-500/5 p-2 text-blue-300">
            Papier : {paperActions.map((signal) => signal.symbol + ' · ' + (signal.paper_status === 'PENDING_BUY' ? 'achat préparé' : 'vente préparée')).join(' ; ')}
          </div>
        )}

        {missing.length > 0 && (
          <details className="rounded border border-amber-500/25 bg-amber-500/5 p-2 text-amber-300">
            <summary className="cursor-pointer">{missing.length} titre(s) sans cours vérifiés · univers incomplet</summary>
            <p className="mt-2">Ils sont exclus du papier. Les achats réels restent bloqués sur cet univers.</p>
            <ul className="mt-1 list-disc pl-4">
              {missing.map((signal) => {
                const date = signal.reasons?.join(' ').match(/missing XNYS bar (\d{4}-\d{2}-\d{2})/)?.[1];
                return <li key={signal.symbol}>{signal.symbol} · {date ? 'bougie du ' + date + ' absente' : 'cours quotidien manquant'}</li>;
              })}
            </ul>
          </details>
        )}

        {repairs.length > 0 && (
          <details className="rounded border border-blue-500/20 bg-blue-500/5 p-2 text-blue-300">
            <summary className="cursor-pointer">{repairs.length} bougie(s) complétée(s) depuis Nasdaq · vérification disponible</summary>
            <p className="mt-2">Yahoo reste la source principale. Chaque cours de secours a été comparé aux séances voisines et conservé avec sa provenance.</p>
            <ul className="mt-1 list-disc pl-4">
              {repairs.map((repair) => (
                <li key={repair.symbol + repair.date}>{repair.symbol} · {repair.date} · <a className="underline" href={repair.source_url} target="_blank" rel="noreferrer">source Nasdaq</a></li>
              ))}
            </ul>
          </details>
        )}

        <section className="space-y-2">
          <h3 className="font-semibold text-white">À examiner · {positive.length}</h3>
          {positive.length > 0
            ? positive.map((candidate) => <Candidate key={candidate.symbol} candidate={candidate} onSymbolClick={onSymbolClick} />)
            : <p className="text-[--text-muted]">Aucun signal au score prudent positif sur cette séance.</p>}
        </section>

        {other.length > 0 && (
          <details className="border-t border-white/10 pt-3">
            <summary className="cursor-pointer text-[--text-secondary]">Autres déclenchements techniques · {other.length}</summary>
            <div className="mt-3 space-y-2">
              {other.map((candidate) => <Candidate key={candidate.symbol} candidate={candidate} onSymbolClick={onSymbolClick} />)}
            </div>
          </details>
        )}

        <details className="border-t border-white/10 pt-3">
          <summary className="cursor-pointer text-[--text-secondary]">Détails par stratégie · RSI(2), IBS, TOM</summary>
          <div className="mt-4">
            {Object.entries(strategies).map(([key, strat]) => (
              <StrategySection key={key} strategyKey={key} strategyData={strat} onSymbolClick={onSymbolClick} />
            ))}
          </div>
        </details>
      </div>
    </Card>
  );
}
