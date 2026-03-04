import React, { useMemo } from 'react';
import Card from '../ui/Card';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';

export default function RobustnessHeatmap({ strategy, symbol, universe }) {
  const { data, loading, error, refetch } = useApi(
    () => api.backtestRobustness(strategy, symbol, universe),
    [strategy, symbol, universe]
  );

  const matrix = useMemo(() => {
    if (!data?.robustness) return null;
    
    // We expect robustness to have: x_axis, y_axis, values, x_label, y_label
    return data.robustness;
  }, [data]);

  if (loading) return <Card title="Robustness Heatmap"><LoadingState rows={6} /></Card>;
  if (error) return <Card title="Robustness Heatmap"><ErrorState message={error} onRetry={refetch} /></Card>;
  if (!matrix) return null;

  const getBgColor = (pf) => {
    if (pf <= 0) return 'bg-red-500/20';
    if (pf < 1.0) return 'bg-amber-500/20';
    if (pf < 1.2) return 'bg-green-500/20';
    if (pf < 1.5) return 'bg-green-500/40';
    return 'bg-green-500/70';
  };

  return (
    <Card 
      title={`Robustness Matrix: ${symbol}`} 
      subtitle={`${matrix.y_label} vs ${matrix.x_label} (Profit Factor)`}
    >
      <div className="overflow-x-auto pb-4">
        <div className="inline-block min-w-full align-middle">
          <table className="min-w-full border-separate border-spacing-1">
            <thead>
              <tr>
                <th className="p-2 text-[10px] text-[--text-muted] text-left italic">
                  {matrix.y_label} \ {matrix.x_label}
                </th>
                {matrix.x_axis.map(x => (
                  <th key={x} className="p-2 text-[10px] font-bold text-white bg-white/5 rounded-md min-w-[60px]">
                    {x}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.y_axis.map((y, yIdx) => (
                <tr key={y}>
                  <td className="p-2 text-[10px] font-bold text-white bg-white/5 rounded-md">
                    {y}
                  </td>
                  {matrix.values[yIdx].map((pf, xIdx) => (
                    <td 
                      key={`${yIdx}-${xIdx}`} 
                      className={`p-3 text-center text-xs font-bold text-white rounded-md transition-transform hover:scale-110 cursor-help ${getBgColor(pf)}`}
                      title={`PF: ${pf.toFixed(2)} for ${matrix.y_label}=${y}, ${matrix.x_label}=${matrix.x_axis[xIdx]}`}
                    >
                      {pf > 0 ? pf.toFixed(2) : '0'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Legend */}
      <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-white/5 pt-4">
        <span className="text-[10px] text-[--text-muted] uppercase font-bold tracking-widest">Légende PF :</span>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-red-500/20 rounded-sm" />
          <span className="text-[10px] text-[--text-muted]">≤ 0</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-amber-500/20 rounded-sm" />
          <span className="text-[10px] text-[--text-muted]">0 - 1.0</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-green-500/20 rounded-sm" />
          <span className="text-[10px] text-[--text-muted]">1.0 - 1.2</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-green-500/40 rounded-sm" />
          <span className="text-[10px] text-[--text-muted]">1.2 - 1.5</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-green-500/70 rounded-sm" />
          <span className="text-[10px] text-[--text-muted]">&gt; 1.5</span>
        </div>
      </div>
    </Card>
  );
}
