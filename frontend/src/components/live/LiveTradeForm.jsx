import { useState } from 'react';
import { api } from '../../api/client';
import { useToasts } from '../../hooks/useToasts.jsx';
import { X, Save, AlertCircle } from 'lucide-react';

export default function LiveTradeForm({ prefill = {}, onDone, onCancel }) {
  const { addToast } = useToasts();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState({
    strategy: prefill.strategy || 'rsi2',
    symbol: prefill.symbol || '',
    entry_date: prefill.entry_date || new Date().toISOString().split('T')[0],
    entry_price: prefill.entry_price || '',
    shares: prefill.shares || '',
    fees_entry: prefill.fees_entry || '1.00',
    paper_position_id: prefill.paper_position_id || null
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.liveOpen(formData);
      addToast(`Trade ${formData.symbol} enregistré avec succès !`);
      onDone();
    } catch (err) {
      setError(err.message);
      addToast("Erreur lors de l'enregistrement", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md glass-card rounded-2xl shadow-2xl border border-white/10 overflow-hidden">
        <div className="flex items-center justify-between p-6 border-b border-white/5 bg-[--bg-card]/50">
          <h2 className="text-xl font-bold text-white tracking-tight">Log Real Trade</h2>
          <button onClick={onCancel} className="p-2 rounded-full hover:bg-white/5 text-[--text-muted] transition-colors"><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex gap-2">
              <AlertCircle size={14} className="shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] text-[--text-muted] uppercase font-bold px-1">Symbol</label>
              <input 
                required 
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-green-500/50 outline-none transition-all"
                value={formData.symbol}
                onChange={e => setFormData({...formData, symbol: e.target.value.toUpperCase()})}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] text-[--text-muted] uppercase font-bold px-1">Strategy</label>
              <select 
                className="w-full bg-[#1a1d27] border border-white/10 rounded-lg px-3 py-2 text-white focus:border-green-500/50 outline-none transition-all"
                value={formData.strategy}
                onChange={e => setFormData({...formData, strategy: e.target.value})}
              >
                <option value="rsi2">RSI(2)</option>
                <option value="ibs">IBS</option>
                <option value="tom">TOM</option>
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] text-[--text-muted] uppercase font-bold px-1">Entry Date</label>
            <input 
              required type="date"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-green-500/50 outline-none transition-all"
              value={formData.entry_date}
              onChange={e => setFormData({...formData, entry_date: e.target.value})}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] text-[--text-muted] uppercase font-bold px-1">Entry Price</label>
              <input 
                required type="number" step="0.01"
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-green-500/50 outline-none transition-all"
                value={formData.entry_price}
                onChange={e => setFormData({...formData, entry_price: e.target.value})}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] text-[--text-muted] uppercase font-bold px-1">Shares</label>
              <input 
                required type="number"
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-green-500/50 outline-none transition-all"
                value={formData.shares}
                onChange={e => setFormData({...formData, shares: e.target.value})}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] text-[--text-muted] uppercase font-bold px-1">Entry Fees ($)</label>
            <input 
              required type="number" step="0.01"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white focus:border-green-500/50 outline-none transition-all"
              value={formData.fees_entry}
              onChange={e => setFormData({...formData, fees_entry: e.target.value})}
            />
          </div>

          <div className="pt-4 flex gap-3">
            <button 
              type="button" 
              onClick={onCancel}
              className="flex-1 px-4 py-2.5 rounded-xl border border-white/5 text-[--text-muted] font-bold text-sm hover:bg-white/5 transition-all cursor-pointer"
            >
              Annuler
            </button>
            <button 
              disabled={loading}
              className="flex-1 px-4 py-2.5 rounded-xl bg-green-500/10 text-green-400 border border-green-500/30 font-bold text-sm hover:bg-green-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer shadow-[0_0_20px_rgba(34,197,94,0.1)]"
            >
              {loading ? <RefreshCw size={16} className="animate-spin" /> : <Save size={16} />}
              Enregistrer
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
