import React, { useState } from 'react';
import { cn } from '../../lib/utils';

export default function AssetIcon({ symbol, className, size = 'md' }) {
  const [error, setError] = useState(false);

  const sizeClasses = {
    xs: 'w-4 h-4 text-[8px]',
    sm: 'w-6 h-6 text-[10px]',
    md: 'w-10 h-10 text-xs',
    lg: 'w-14 h-14 text-sm',
  };

  const fallback = symbol ? symbol.substring(0, 2).toUpperCase() : '??';
  
  // No complex logic here, just point to our robust proxy
  const proxyUrl = symbol && !symbol.includes('=X') ? `/api/market/asset/${symbol}/logo` : null;

  if (proxyUrl && !error) {
    return (
      <div className={cn(
        "rounded-lg bg-white overflow-hidden flex items-center justify-center shrink-0 border border-white/10 shadow-sm",
        sizeClasses[size],
        className
      )}>
        <img 
          src={proxyUrl} 
          alt={symbol}
          className="w-full h-full object-contain p-1"
          onError={() => setError(true)}
        />
      </div>
    );
  }

  const getFallbackColor = (str) => {
    const colors = [
      'bg-blue-500/20 text-blue-400 border-blue-500/30',
      'bg-purple-500/20 text-purple-400 border-purple-500/30',
      'bg-amber-500/20 text-amber-400 border-amber-500/30',
      'bg-green-500/20 text-green-400 border-green-500/30',
      'bg-pink-500/20 text-pink-400 border-pink-500/30',
    ];
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <div className={cn(
      "rounded-lg flex items-center justify-center shrink-0 border font-bold tracking-tighter",
      sizeClasses[size],
      getFallbackColor(symbol || '??'),
      className
    )}>
      {fallback}
    </div>
  );
}
