import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, ReferenceLine, ResponsiveContainer, AreaChart, Area } from 'recharts';

const INITIAL_DATA = [
  { day: 1, price: 105, rsi: 65 },
  { day: 2, price: 104, rsi: 50 },
  { day: 3, price: 106, rsi: 70 },
  { day: 4, price: 102, rsi: 30 },
  { day: 5, price: 98, rsi: 15 },
];

export default function RSI2Visualizer() {
  const [currentPrice, setCurrentPrice] = useState(96);
  const rsi = Math.max(2, Math.min(98, 15 - (98 - currentPrice) * 5));
  const isBuy = rsi < 10;
  
  const data = [...INITIAL_DATA, { day: 6, price: currentPrice, rsi }];

  return (
    <div className="bg-white/5 rounded-2xl p-6 border border-white/5 space-y-6">
      <div className="flex justify-between items-center">
        <h4 className="text-sm font-bold text-white uppercase tracking-wider">Playground RSI(2)</h4>
        <div className={`px-3 py-1 rounded-full text-[10px] font-bold ${isBuy ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-white/5 text-[--text-muted]'}`}>
          {isBuy ? 'SURVENDU : ACHAT' : 'ATTENTE'}
        </div>
      </div>

      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.1}/>
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <XAxis dataKey="day" hide />
            <YAxis domain={['dataMin - 5', 'dataMax + 5']} hide />
            <ReferenceLine y={100} stroke="rgba(255,255,255,0.1)" label={{ position: 'right', value: 'SMA 200', fill: '#64748b', fontSize: 10 }} />
            <Area type="monotone" dataKey="price" stroke="#22c55e" fillOpacity={1} fill="url(#colorPrice)" strokeWidth={2} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="space-y-4">
        <div className="flex justify-between items-end">
          <div className="space-y-1">
            <span className="text-[10px] text-[--text-muted] uppercase tracking-widest">RSI(2) Simulée</span>
            <div className={`text-4xl font-black tabular-nums transition-colors ${isBuy ? 'text-green-400' : 'text-white'}`}>
              {rsi.toFixed(1)}
            </div>
          </div>
          <div className="text-right space-y-1">
            <span className="text-[10px] text-[--text-muted] uppercase tracking-widest">Prix Actuel</span>
            <div className="text-xl font-bold tabular-nums text-white">
              ${currentPrice.toFixed(2)}
            </div>
          </div>
        </div>

        <input 
          type="range" 
          min="90" 
          max="110" 
          step="0.1" 
          value={currentPrice} 
          onChange={(e) => setCurrentPrice(parseFloat(e.target.value))}
          className="w-full accent-green-500"
        />
        
        <p className="text-xs text-[--text-muted] leading-relaxed italic">
          Glissez le prix vers le bas pour simuler un "crash" temporaire. Si le RSI(2) descend sous 10 alors que nous sommes en tendance haussière (au-dessus de la ligne grise), c'est une opportunité d'achat "Mean Reversion".
        </p>
      </div>
    </div>
  );
}
