import React, { useState } from 'react';
import { motion } from 'framer-motion';

export default function IBSVisualizer() {
  const [closePercent, setClosePercent] = useState(0.15); // 0 to 1
  const ibs = closePercent;
  const isBuy = ibs < 0.2;

  return (
    <div className="bg-white/5 rounded-2xl p-6 border border-white/5 space-y-6">
      <div className="flex justify-between items-center">
        <h4 className="text-sm font-bold text-white uppercase tracking-wider">Playground IBS</h4>
        <div className={`px-3 py-1 rounded-full text-[10px] font-bold ${isBuy ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-white/5 text-[--text-muted]'}`}>
          {isBuy ? 'SIGNAL ACHAT DÉTECTÉ' : 'PAS DE SIGNAL'}
        </div>
      </div>

      <div className="flex gap-12 items-center justify-center py-8">
        {/* Candlestick visualization */}
        <div className="relative w-12 h-64 flex flex-col items-center">
          <div className="w-1 h-full bg-[--text-muted]/30 rounded-full" /> {/* Wick */}
          <div className="absolute top-0 w-8 h-1 bg-white/50 rounded-full" title="High" />
          <div className="absolute bottom-0 w-8 h-1 bg-white/50 rounded-full" title="Low" />
          
          {/* The Body (Simplified to a range from Low to Close) */}
          <motion.div 
            className={`absolute bottom-0 w-6 rounded-sm border ${isBuy ? 'bg-green-500/40 border-green-500/60' : 'bg-white/20 border-white/30'}`}
            initial={false}
            animate={{ height: `${closePercent * 100}%` }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          />
          
          {/* Close Marker (Interactive) */}
          <motion.div 
            className="absolute left-1/2 -translate-x-1/2 w-10 h-4 bg-white border-2 border-black rounded shadow-lg z-10 cursor-grab active:cursor-grabbing"
            style={{ bottom: `calc(${closePercent * 100}% - 8px)` }}
          />
        </div>

        {/* Math explanation */}
        <div className="flex-1 space-y-4 max-w-[200px]">
          <div className="space-y-1">
            <span className="text-[10px] text-[--text-muted] uppercase">Valeur IBS</span>
            <div className="text-4xl font-black tabular-nums text-white">
              {ibs.toFixed(2)}
            </div>
          </div>
          <p className="text-xs text-[--text-muted] leading-relaxed">
            L'IBS mesure où le prix clôture par rapport au range (Haut - Bas). 
            <strong> IBS &lt; 0.20</strong> signifie que nous avons clôturé dans les 20% les plus bas du jour.
          </p>
          <input 
            type="range" 
            min="0" 
            max="1" 
            step="0.01" 
            value={closePercent} 
            onChange={(e) => setClosePercent(parseFloat(e.target.value))}
            className="w-full accent-green-500"
          />
        </div>
      </div>
    </div>
  );
}
