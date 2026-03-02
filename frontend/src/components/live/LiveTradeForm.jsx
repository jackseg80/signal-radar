import { useState } from 'react';
import { api } from '../../api/client';
import { STRATEGY_LABELS } from '../../utils/format';

const STRATEGIES = ['rsi2', 'ibs', 'tom'];

export default function LiveTradeForm({ mode = 'open', prefill = {}, onDone, onCancel }) {
  const [strategy, setStrategy] = useState(prefill.strategy || STRATEGIES[0]);
  const [symbol, setSymbol] = useState(prefill.symbol || '');
  const [date, setDate] = useState(prefill.date || new Date().toISOString().slice(0, 10));
  const [price, setPrice] = useState(prefill.price || '');
  const [shares, setShares] = useState(prefill.shares || '');
  const [fees, setFees] = useState(prefill.fees || '1');
  const [notes, setNotes] = useState(prefill.notes || '');
  const [paperId, setPaperId] = useState(prefill.paper_position_id || '');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const isOpen = mode === 'open';
  const title = isOpen ? 'Log Real Trade' : 'Close Trade';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isOpen) {
        await api.liveOpen({
          strategy, symbol: symbol.toUpperCase(), entry_date: date,
          entry_price: parseFloat(price), shares: parseFloat(shares),
          fees: parseFloat(fees) || 0, notes,
          ...(paperId ? { paper_position_id: parseInt(paperId) } : {}),
        });
      } else {
        await api.liveClose({
          strategy, symbol: symbol.toUpperCase(), exit_date: date,
          exit_price: parseFloat(price), fees: parseFloat(fees) || 0,
        });
      }
      onDone?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass = 'w-full bg-[--bg-primary] border border-[--border-subtle] rounded px-3 py-1.5 text-sm text-[--text-primary] focus:border-green-500/50 focus:outline-none';
  const labelClass = 'text-xs text-[--text-muted] uppercase tracking-wider mb-1';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onCancel}>
      <div
        className="bg-[--bg-card] border border-[--border-subtle] rounded-xl p-6 w-full max-w-md shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold text-[--text-primary] mb-4" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          {title}
        </h3>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className={labelClass}>Strategy</div>
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className={inputClass} disabled={!isOpen}>
                {STRATEGIES.map((s) => (
                  <option key={s} value={s}>{STRATEGY_LABELS[s] || s}</option>
                ))}
              </select>
            </div>
            <div>
              <div className={labelClass}>Symbol</div>
              <input value={symbol} onChange={(e) => setSymbol(e.target.value)} className={inputClass} placeholder="META" required disabled={!isOpen} />
            </div>
          </div>

          <div>
            <div className={labelClass}>{isOpen ? 'Entry Date' : 'Exit Date'}</div>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} required />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className={labelClass}>{isOpen ? 'Entry $' : 'Exit $'}</div>
              <input type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} className={inputClass} placeholder="612.30" required />
            </div>
            {isOpen && (
              <div>
                <div className={labelClass}>Shares</div>
                <input type="number" step="1" value={shares} onChange={(e) => setShares(e.target.value)} className={inputClass} placeholder="8" required />
              </div>
            )}
            <div>
              <div className={labelClass}>Fees $</div>
              <input type="number" step="0.01" value={fees} onChange={(e) => setFees(e.target.value)} className={inputClass} placeholder="1.00" />
            </div>
          </div>

          {isOpen && (
            <div>
              <div className={labelClass}>Notes</div>
              <input value={notes} onChange={(e) => setNotes(e.target.value)} className={inputClass} placeholder="Optional notes" />
            </div>
          )}

          {error && <div className="text-red-400 text-xs">{error}</div>}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 rounded border border-[--border-subtle] text-sm text-[--text-secondary] hover:bg-white/5 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 rounded bg-green-600 text-white text-sm font-medium hover:bg-green-500 transition-colors cursor-pointer disabled:opacity-50"
            >
              {submitting ? 'Saving...' : isOpen ? 'Open Trade' : 'Close Trade'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
