import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts';
import { formatPnl } from '../../utils/format';
import { parseISO, getDay } from 'date-fns';

const DAYS = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];

export default function JournalCharts({ entries }) {
  // 1. PnL Distribution (Histogram)
  const distributionData = useMemo(() => {
    if (!entries) return [];
    const closed = entries.filter(e => e.status === 'closed');
    if (closed.length === 0) return [];

    const bins = {};
    const binSize = 50; // $50 buckets

    closed.forEach(e => {
      const pnl = e.pnl_dollars || 0;
      const bin = Math.floor(pnl / binSize) * binSize;
      bins[bin] = (bins[bin] || 0) + 1;
    });

    return Object.entries(bins)
      .map(([bin, count]) => ({ bin: Number(bin), count }))
      .sort((a, b) => a.bin - b.bin);
  }, [entries]);

  // 2. Performance by Weekday
  const weekdayData = useMemo(() => {
    if (!entries) return [];
    const closed = entries.filter(e => e.status === 'closed');
    
    const days = [1, 2, 3, 4, 5].map(d => ({
      day: DAYS[d],
      pnl: 0,
      trades: 0
    }));

    closed.forEach(e => {
      const dayIdx = getDay(parseISO(e.entry_date));
      if (dayIdx >= 1 && dayIdx <= 5) {
        days[dayIdx - 1].pnl += (e.pnl_dollars || 0);
        days[dayIdx - 1].trades += 1;
      }
    });

    return days;
  }, [entries]);

  if (!entries || entries.filter(e => e.status === 'closed').length === 0) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      {/* PnL Distribution */}
      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
        <h4 className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mb-6">Distribution des Gains/Pertes</h4>
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={distributionData}>
              <XAxis 
                dataKey="bin" 
                fontSize={10} 
                stroke="#64748b" 
                tickFormatter={(v) => `${v}$`}
              />
              <YAxis fontSize={10} stroke="#64748b" />
              <Tooltip 
                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '10px' }}
              />
              <Bar dataKey="count">
                {distributionData.map((entry, index) => (
                  <Cell key={index} fill={entry.bin >= 0 ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Weekday Performance */}
      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
        <h4 className="text-[10px] font-bold text-[--text-muted] uppercase tracking-widest mb-6">Performance par Jour d'Entrée</h4>
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={weekdayData}>
              <XAxis dataKey="day" fontSize={10} stroke="#64748b" />
              <YAxis fontSize={10} stroke="#64748b" tickFormatter={(v) => `${v}$`} />
              <Tooltip 
                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '10px' }}
                formatter={(value) => [formatPnl(value), 'PnL Total']}
              />
              <Bar dataKey="pnl">
                {weekdayData.map((entry, index) => (
                  <Cell key={index} fill={entry.pnl >= 0 ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
