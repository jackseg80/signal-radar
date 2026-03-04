import React, { useState, useEffect, useCallback } from 'react';
import { Search, Command, Activity, ArrowRight, X } from 'lucide-react';
import { api } from '../../api/client';
import { useAssetView } from '../../hooks/useAssetView';

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(false);
  const { openAsset } = useAssetView();

  // Listen for Cmd+K or Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(prev => !prev);
      }
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Fetch asset list when opening
  useEffect(() => {
    if (isOpen && assets.length === 0) {
      setLoading(true);
      api.marketOverview()
        .then(data => {
          setAssets(data.assets || []);
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, assets.length]);

  const filteredAssets = query === '' 
    ? assets.slice(0, 10) 
    : assets.filter(a => a.symbol.toLowerCase().includes(query.toLowerCase())).slice(0, 15);

  const handleSelect = (symbol) => {
    openAsset(symbol);
    setIsOpen(false);
    setQuery('');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh] px-4 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={() => setIsOpen(false)}>
      <div 
        className="w-full max-w-xl glass-card rounded-2xl shadow-2xl border border-white/10 overflow-hidden animate-slide-up"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center px-4 border-b border-white/5 bg-white/[0.02]">
          <Search size={20} className="text-[--text-muted]" />
          <input
            autoFocus
            className="flex-1 bg-transparent border-none py-4 px-3 text-white outline-none placeholder:text-[--text-muted] text-sm"
            placeholder="Rechercher un actif... (ex: AAPL, META)"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-white/5 border border-white/10 text-[10px] text-[--text-muted] font-bold">
            <Command size={10} /> K
          </div>
          <button onClick={() => setIsOpen(false)} className="ml-3 p-1 hover:bg-white/5 rounded-full text-[--text-muted] transition-colors cursor-pointer">
            <X size={16} />
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto p-2 custom-scrollbar">
          {loading ? (
            <div className="py-12 text-center text-[--text-muted] animate-pulse text-xs uppercase tracking-widest font-bold">Chargement de l'univers...</div>
          ) : filteredAssets.length > 0 ? (
            <div className="grid grid-cols-1 gap-1">
              {filteredAssets.map(asset => (
                <button
                  key={asset.symbol}
                  onClick={() => handleSelect(asset.symbol)}
                  className="flex items-center justify-between w-full p-3 rounded-xl hover:bg-white/5 text-left transition-all group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-green-500/10 text-green-400 group-hover:bg-green-500/20 transition-colors">
                      <Activity size={16} />
                    </div>
                    <div>
                      <div className="font-bold text-white text-sm tracking-tight">{asset.symbol}</div>
                      <div className="text-[10px] text-[--text-muted] uppercase font-medium">Daily OHLCV</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                    <span className="text-[10px] font-bold text-green-400 uppercase tracking-widest">Ouvrir</span>
                    <ArrowRight size={14} className="text-green-400" />
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="py-12 text-center text-[--text-muted] text-xs">Aucun actif trouvé pour "{query}"</div>
          )}
        </div>

        <div className="p-3 border-t border-white/5 bg-white/[0.01] flex justify-between items-center text-[9px] text-[--text-muted] uppercase font-bold tracking-widest">
          <div className="flex gap-4">
            <span className="flex items-center gap-1.5"><ArrowRight size={10} className="rotate-90" /> Naviguer</span>
            <span className="flex items-center gap-1.5"><ArrowRight size={10} className="-rotate-180" /> Sélectionner</span>
          </div>
          <span>Signal Radar Search</span>
        </div>
      </div>
    </div>
  );
}
