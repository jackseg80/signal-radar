import { useState } from 'react';
import { api } from '../../api/client';
import { useToasts } from '../../hooks/useToasts.jsx';
import { X } from 'lucide-react';

const today = () => {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, '0');
  return now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate());
};

export default function LiveTradeForm({ mode = 'open', prefill = {}, onDone, onCancel }) {
  const { addToast } = useToasts();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    strategy: prefill.strategy || 'rsi2',
    symbol: prefill.symbol || '',
    instrument_type: prefill.instrument_type || 'stock',
    signal_session: prefill.signal_session || '',
    entry_date: prefill.entry_date || today(),
    entry_price: prefill.entry_price || '',
    shares: prefill.shares || '',
    entry_fees: '',
    notes: '',
    exit_date: today(),
    exit_price: prefill.current_price || '',
    exit_fees: '',
    financing_cost: '',
  });
  const close = mode === 'close';
  const set = (name) => (event) => setForm({ ...form, [name]: event.target.value });

  const save = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      if (close) {
        await api.liveCloseById(prefill.id, {
          exit_date: form.exit_date,
          exit_price: form.exit_price,
          fees: form.exit_fees === '' ? undefined : form.exit_fees,
          financing_cost: form.financing_cost === '' ? undefined : form.financing_cost,
        });
      } else {
        await api.liveOpen({
          strategy: form.strategy,
          symbol: form.symbol.trim().toUpperCase(),
          instrument_type: form.instrument_type,
          signal_session: form.signal_session || undefined,
          entry_date: form.entry_date,
          entry_price: form.entry_price,
          shares: form.shares,
          fees: form.entry_fees === '' ? undefined : form.entry_fees,
          notes: form.notes || undefined,
        });
      }
      addToast(close ? 'Opération clôturée' : 'Opération enregistrée');
      onDone();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setLoading(false);
    }
  };
  const input = 'w-full rounded-lg border border-white/10 bg-[#1a1d27] px-3 py-2 text-white';

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/80 p-4">
      <div className="glass-card max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-white">{close ? 'Clôturer mon opération' : 'Saisir mon opération'}</h2>
          <button type="button" onClick={onCancel} aria-label="Fermer" className="text-[--text-muted]"><X size={20} /></button>
        </div>
        <p className="mb-4 text-xs text-[--text-muted]">Journal des opérations décidées à partir de Signal Radar uniquement. Aucune transaction n’est envoyée à Saxo.</p>
        <form onSubmit={save} className="space-y-4 text-sm">
          {error && <p role="alert" className="text-red-400">{error}</p>}
          {close ? (
            <>
              <p className="font-semibold text-white">{prefill.symbol} · {prefill.strategy.toUpperCase()} · {prefill.instrument_type === 'cfd' ? 'CFD sur action' : prefill.instrument_type === 'stock' ? 'Action' : 'Instrument à préciser'}</p>
              <label className="block text-[--text-secondary]">Date de clôture<input required type="date" className={input} value={form.exit_date} onChange={set('exit_date')} /></label>
              <label className="block text-[--text-secondary]">Prix de sortie USD<input required type="number" min="0.0001" step="any" className={input} value={form.exit_price} onChange={set('exit_price')} /></label>
              <label className="block text-[--text-secondary]">Frais de sortie réellement facturés USD<input type="number" min="0" step="0.01" className={input} value={form.exit_fees} onChange={set('exit_fees')} placeholder="Laisser vide si inconnus" /></label>
              {prefill.instrument_type === 'cfd' && <label className="block text-[--text-secondary]">Financement CFD réellement facturé USD<input type="number" min="0" step="0.01" className={input} value={form.financing_cost} onChange={set('financing_cost')} placeholder="Laisser vide si inconnu" /></label>}
            </>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-[--text-secondary]">Action<input required className={input} value={form.symbol} onChange={set('symbol')} placeholder="META" /></label>
                <label className="block text-[--text-secondary]">Stratégie principale<select className={input} value={form.strategy} onChange={set('strategy')}><option value="rsi2">RSI(2)</option><option value="ibs">IBS</option><option value="tom">TOM</option></select></label>
              </div>
              <label className="block text-[--text-secondary]">Instrument réellement acheté<select className={input} value={form.instrument_type} onChange={set('instrument_type')}><option value="stock">Action</option><option value="cfd">CFD sur action, acheteur</option></select></label>
              <label className="block text-[--text-secondary]">Date du signal (facultatif)<input type="date" className={input} value={form.signal_session} onChange={set('signal_session')} /></label>
              <p className="text-xs text-[--text-muted]">Le lien au signal sera confirmé si cette action et cette stratégie figurent dans le scan de la date choisie. Sinon la date sera conservée comme référence manuelle.</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-[--text-secondary]">Date d’achat<input required type="date" className={input} value={form.entry_date} onChange={set('entry_date')} /></label>
                <label className="block text-[--text-secondary]">Prix d’achat USD<input required type="number" min="0.0001" step="any" className={input} value={form.entry_price} onChange={set('entry_price')} /></label>
                <label className="block text-[--text-secondary]">Quantité<input required type="number" min="0.000001" step="any" className={input} value={form.shares} onChange={set('shares')} /></label>
                <label className="block text-[--text-secondary]">Frais d’entrée réels USD<input type="number" min="0" step="0.01" className={input} value={form.entry_fees} onChange={set('entry_fees')} placeholder="Laisser vide si inconnus" /></label>
              </div>
              <label className="block text-[--text-secondary]">Note (facultative)<textarea className={input} value={form.notes} onChange={set('notes')} placeholder="Contexte de la décision" /></label>
            </>
          )}
          <p className="text-xs text-amber-300">Un coût laissé vide rend le résultat net provisoire. Saisir 0 uniquement si le coût réel est nul.</p>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onCancel} className="flex-1 rounded-lg border border-white/10 px-3 py-2 text-[--text-secondary]">Annuler</button>
            <button disabled={loading} type="submit" className="flex-1 rounded-lg bg-green-500/20 px-3 py-2 font-semibold text-green-300 disabled:opacity-50">{loading ? 'Enregistrement…' : close ? 'Clôturer' : 'Enregistrer'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
