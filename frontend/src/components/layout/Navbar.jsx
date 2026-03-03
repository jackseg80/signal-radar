import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';
import { formatTimestamp } from '../../utils/format';

export default function Navbar() {
  const { refreshKey, refresh } = useRefresh();
  const { data } = useApi(() => api.signalsToday(), [refreshKey]);

  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);

  useEffect(() => {
    if (scanResult) {
      const timer = setTimeout(() => setScanResult(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [scanResult]);

  const runScanner = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const res = await api.scannerRun();
      setScanResult(res);
      if (res.status === 'completed') {
        refresh();
      }
    } catch (err) {
      setScanResult({ status: 'error', detail: err.message });
    } finally {
      setScanning(false);
    }
  };

  const linkClass = ({ isActive }) =>
    `px-3 py-1.5 rounded text-sm transition-colors ${
      isActive
        ? 'bg-white/10 text-[--text-primary] font-medium'
        : 'text-[--text-muted] hover:text-[--text-secondary]'
    }`;

  return (
    <header className="border-b border-[--glass-border] bg-[--glass-bg] backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 flex items-center h-12 gap-6">
        <span className="font-bold text-base tracking-tight text-green-400 flex items-center gap-2" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse-dot" />
          SIGNAL RADAR
        </span>

        <nav className="flex gap-1">
          <NavLink to="/" className={linkClass} end>Dashboard</NavLink>
          <NavLink to="/backtest" className={linkClass}>Backtest</NavLink>
          <NavLink to="/journal" className={linkClass}>Journal</NavLink>
        </nav>

        <div className="ml-auto flex items-center gap-4 text-xs text-[--text-muted]">
          {data?.scanner_timestamp && (
            <span className="animate-fade-in">Last scan: {formatTimestamp(data.scanner_timestamp)}</span>
          )}

          {scanResult && scanResult.status === 'completed' && (
            <span className="text-green-400 animate-fade-in">Scan OK</span>
          )}
          {scanResult && scanResult.status === 'error' && (
            <span className="text-red-400 animate-fade-in">{scanResult.detail || 'Scan failed'}</span>
          )}

          <button
            onClick={runScanner}
            disabled={scanning}
            className={`px-3 py-1 rounded border transition-all duration-300 cursor-pointer relative overflow-hidden ${
              scanning
                ? 'border-amber-500/40 text-amber-400'
                : 'border-green-500/30 text-[--text-secondary] hover:bg-green-500/10 hover:text-green-400 hover:border-green-500/50'
            }`}
          >
            {scanning && (
              <span className="absolute inset-0 animate-shimmer" />
            )}
            <span className="relative">{scanning ? 'Scanning...' : 'Scan'}</span>
          </button>

          <button
            onClick={refresh}
            className="px-3 py-1 rounded border border-[--border-subtle] text-[--text-secondary] hover:bg-white/5 hover:text-[--text-primary] transition-colors cursor-pointer"
          >
            Refresh
          </button>
        </div>
      </div>
    </header>
  );
}
