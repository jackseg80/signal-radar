import React, { useState, useMemo } from 'react';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isWeekend, addDays, subDays, getDay } from 'date-fns';
import { fr } from 'date-fns/locale';
import { ChevronLeft, ChevronRight, Info } from 'lucide-react';

export default function TOMVisualizer() {
  const [viewDate, setViewDate] = useState(new Date());
  
  const calendarDays = useMemo(() => {
    const start = startOfMonth(viewDate);
    const end = endOfMonth(viewDate);
    const days = eachDayOfInterval({ start, end });
    
    // Simplification for visualization: 
    // Usually entrance is last 5 TRADING days.
    // Exit is first 3 TRADING days.
    
    // Identify potential trading days (non-weekend)
    const tradingDays = days.filter(d => getDay(d) !== 0 && getDay(d) !== 6);
    
    const entryWindow = tradingDays.slice(-5);
    const exitWindow = tradingDays.slice(0, 3);
    
    return days.map(d => {
      const isWknd = isWeekend(d);
      const isEntry = entryWindow.some(ed => format(ed, 'yyyy-MM-dd') === format(d, 'yyyy-MM-dd'));
      const isExit = exitWindow.some(exd => format(exd, 'yyyy-MM-dd') === format(d, 'yyyy-MM-dd'));
      
      return {
        date: d,
        dayNum: format(d, 'd'),
        isWeekend: isWknd,
        isEntry,
        isExit
      };
    });
  }, [viewDate]);

  const changeMonth = (offset) => {
    const next = new Date(viewDate);
    next.setMonth(next.getMonth() + offset);
    setViewDate(next);
  };

  return (
    <div className="bg-white/5 rounded-2xl p-6 border border-white/5 space-y-6">
      <div className="flex justify-between items-center">
        <h4 className="text-sm font-bold text-white uppercase tracking-wider">Playground Calendrier TOM</h4>
        <div className="flex items-center gap-2">
          <button onClick={() => changeMonth(-1)} className="p-1 hover:bg-white/5 rounded-md text-[--text-muted] transition-colors cursor-pointer"><ChevronLeft size={18} /></button>
          <span className="text-xs font-bold text-white min-w-[100px] text-center uppercase tracking-widest">{format(viewDate, 'MMMM yyyy', { locale: fr })}</span>
          <button onClick={() => changeMonth(1)} className="p-1 hover:bg-white/5 rounded-md text-[--text-muted] transition-colors cursor-pointer"><ChevronRight size={18} /></button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1">
        {['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di'].map(d => (
          <div key={d} className="text-[10px] text-center text-[--text-muted] font-bold py-2">{d}</div>
        ))}
        
        {/* Padding for first day of month */}
        {Array.from({ length: (getDay(startOfMonth(viewDate)) + 6) % 7 }).map((_, i) => (
          <div key={`pad-${i}`} className="h-12" />
        ))}

        {calendarDays.map((d, i) => (
          <div 
            key={i} 
            className={`h-12 rounded-lg flex flex-col items-center justify-center relative transition-all border ${
              d.isEntry ? 'bg-green-500/20 border-green-500/40 text-green-400 shadow-[0_0_15px_rgba(34,197,94,0.1)]' :
              d.isExit ? 'bg-blue-500/20 border-blue-500/40 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.1)]' :
              d.isWeekend ? 'bg-white/[0.01] border-transparent opacity-20' :
              'bg-white/[0.03] border-transparent text-[--text-secondary]'
            }`}
          >
            <span className="text-xs font-bold">{d.dayNum}</span>
            {d.isEntry && <span className="text-[7px] uppercase font-black absolute bottom-1">BUY</span>}
            {d.isExit && <span className="text-[7px] uppercase font-black absolute bottom-1 text-blue-400">EXIT</span>}
          </div>
        ))}
      </div>

      <div className="space-y-3 pt-4 border-t border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-[10px] text-[--text-secondary]">Fenêtre d'entrée (5 derniers jours de bourse)</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-blue-500" />
          <span className="text-[10px] text-[--text-secondary]">Fenêtre de sortie (3 premiers jours de bourse)</span>
        </div>
        <div className="mt-4 p-3 rounded-lg bg-blue-500/5 border border-blue-500/10 flex gap-3">
          <Info size={14} className="text-blue-400 shrink-0" />
          <p className="text-[10px] text-[--text-muted] leading-relaxed italic">
            Les week-ends et jours fériés sont exclus du calcul. C'est pourquoi la fenêtre peut sembler varier sur le calendrier civil.
          </p>
        </div>
      </div>
    </div>
  );
}
