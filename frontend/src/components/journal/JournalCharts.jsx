import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';
import Card from '../ui/Card';

export default function JournalCharts({ entries }) {
  const closedTrades = useMemo(() => 
    entries.filter(e => e.status === 'closed' && e.pnl_dollars != null), 
    [entries]
  );

  // 1. PnL Distribution
  const pnlData = useMemo(() => {
    if (closedTrades.length === 0) return [];
    
    // Create bins for PnL
    const bins = {};
    const binSize = 50; // $50 increments
    
    closedTrades.forEach(t => {
      const bin = Math.floor(t.pnl_dollars / binSize) * binSize;
      bins[bin] = (bins[bin] || 0) + 1;
    });
    
    return Object.entries(bins)
      .map(([bin, count]) => ({
        range: `${bin}$`,
        value: Number(bin),
        count
      }))
      .sort((a, b) => a.value - b.value);
  }, [closedTrades]);

  // 2. Day of Week Performance
  const weekdayData = useMemo(() => {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const stats = days.map(d => ({ name: d, pnl: 0, count: 0 }));
    
    closedTrades.forEach(t => {
      const date = new Date(t.entry_date);
      const dayIdx = date.getDay();
      stats[dayIdx].pnl += t.pnl_dollars;
      stats[dayIdx].count += 1;
    });
    
    return stats.filter(s => s.count > 0);
  }, [closedTrades]);

  if (closedTrades.length === 0) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      <Card title="Distribution des PnL" subtitle="Nombre de trades par tranche de gain/perte" noScroll>
        <div className="h-[250px] min-h-[250px] w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={pnlData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
              <XAxis dataKey="range" tick={{fill: '#64748b', fontSize: 10}} axisLine={false} />
              <YAxis tick={{fill: '#64748b', fontSize: 10}} axisLine={false} tickLine={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid #ffffff10', borderRadius: '12px' }}
                itemStyle={{ color: '#fff', fontSize: '12px' }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {pnlData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.value >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.6} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="Performance par Jour" subtitle="PnL cumulé par jour d'entrée" noScroll>
        <div className="h-[250px] min-h-[250px] w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={weekdayData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
              <XAxis dataKey="name" tick={{fill: '#64748b', fontSize: 10}} axisLine={false} />
              <YAxis tick={{fill: '#64748b', fontSize: 10}} axisLine={false} tickLine={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1a1d27', border: '1px solid #ffffff10', borderRadius: '12px' }}
                itemStyle={{ color: '#fff', fontSize: '12px' }}
                formatter={(value) => [`$${value.toFixed(2)}`, 'PnL']}
              />
              <ReferenceLine y={0} stroke="#ffffff10" />
              <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                {weekdayData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.6} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}
