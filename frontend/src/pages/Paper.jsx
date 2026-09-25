import { useApi } from '../hooks/useApi';
import { useRefresh } from '../hooks/useRefresh.jsx';
import { useAssetView } from '../hooks/useAssetView.jsx';
import { api } from '../api/client';
import OpenPositions from '../components/positions/OpenPositions';
import ClosedTrades from '../components/positions/ClosedTrades';
import SignalFollowPositions from '../components/positions/SignalFollowPositions';
import PaperEquity from '../components/performance/PaperEquity';

export default function Paper() {
  const { refreshKey } = useRefresh();
  const { openAsset } = useAssetView();
  const { data, error } = useApi(() => api.performanceSummary(), [refreshKey]);
  const { data: settings } = useApi(() => api.getSettings(), []);
  const paper = data?.paper;
  return (
    <div className="space-y-6 pb-16">
      <header>
        <h1 className="text-2xl font-bold text-white">Simulation papier</h1>
        <p className="text-sm text-[--text-muted]">Portefeuille théorique commun, avec un capital initial de {settings?.initial_capital?.toLocaleString('fr-CH') ?? '5 000'} USD. Ce capital ne limite pas les signaux du Radar.</p>
      </header>
      {error && <p className="text-red-400">{error}</p>}
      {paper && <section className="grid gap-4 sm:grid-cols-3" aria-label="Résultats papier">
        <div className="glass-card rounded-xl p-4"><p className="text-xs text-[--text-muted]">Résultat réalisé</p><strong className="text-xl text-white">{paper.total_pnl?.toFixed(2)} USD</strong></div>
        <div className="glass-card rounded-xl p-4"><p className="text-xs text-[--text-muted]">Trades clôturés</p><strong className="text-xl text-white">{paper.n_trades}</strong></div>
        <div className="glass-card rounded-xl p-4"><p className="text-xs text-[--text-muted]">Positions ouvertes</p><strong className="text-xl text-white">{paper.n_open}</strong></div>
      </section>}
      <PaperEquity />
      <OpenPositions onSymbolClick={openAsset} />
      <ClosedTrades onSymbolClick={openAsset} />
      <SignalFollowPositions onSymbolClick={openAsset} />
    </div>
  );
}
