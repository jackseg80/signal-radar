import { useEffect, useState } from 'react';
import { api } from '../../api/client';

export default function AccountConfirmation({ refresh }) {
  const [session, setSession] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [cash, setCash] = useState('');
  const [holdings, setHoldings] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.accountCurrent().then((data) => {
      setSession(data.source_session);
      setConfirmation(data.confirmation);
      setCash(data.confirmation?.cash_usd ?? '');
      setHoldings((data.confirmation?.holdings ?? []).join(', '));
    }).catch((error) => setMessage(error.message));
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      const saved = await api.accountConfirm({
        source_session: session,
        cash_usd: Number(cash),
        holdings: holdings.split(/[;,\s]+/).map((s) => s.trim().toUpperCase()).filter(Boolean),
      });
      setConfirmation(saved);
      setMessage('Compte confirmé pour cette séance. Recalcul des signaux demandé.');
      await api.scannerRun();
      refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4" aria-label="Confirmation du compte Saxo">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-bold text-white">Compte Saxo · séance {session ?? '…'}</h2>
        <span className={confirmation ? 'text-green-400 text-xs' : 'text-amber-400 text-xs'}>
          {confirmation ? `Compte renseigné le ${new Date(confirmation.confirmed_at).toLocaleString('fr-CH')}` : 'Facultatif pour le papier et le suivi virtuel'}
        </span>
      </div>
      <p className="mt-1 text-xs text-[--text-muted]">Le portefeuille papier commun et le suivi virtuel des signaux fonctionnent sans saisie Saxo. Pour évaluer un achat réel, indiquez uniquement le cash USD disponible et tous les titres réellement détenus chez Saxo, même hors Signal Radar. Cette confirmation ne lève pas les contrôles des cours, de la validation et des frais. Ne saisissez pas de données fictives.</p>
      <form onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-3">
        <label className="text-xs text-[--text-secondary]">Cash USD
          <input className="mt-1 block w-36 rounded border border-white/10 bg-black/30 p-2 text-white" type="number" min="0" step="0.01" required value={cash} onChange={(e) => setCash(e.target.value)} />
        </label>
        <label className="min-w-52 flex-1 text-xs text-[--text-secondary]">Titres détenus (symboles séparés par virgule ; laisser vide si aucun)
          <input className="mt-1 block w-full rounded border border-white/10 bg-black/30 p-2 text-white" value={holdings} onChange={(e) => setHoldings(e.target.value)} placeholder="AAPL, MSFT" />
        </label>
        <button disabled={saving || !session} type="submit" className="rounded bg-amber-500 px-4 py-2 text-xs font-bold text-black disabled:opacity-40">{saving ? 'Enregistrement…' : 'Confirmer le compte'}</button>
      </form>
      {message && <p className="mt-2 text-xs text-amber-300" role="status">{message}</p>}
    </section>
  );
}
