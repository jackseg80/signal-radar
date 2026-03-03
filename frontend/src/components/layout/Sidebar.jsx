import React from 'react';
import { NavLink } from 'react-router-dom';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';
import { formatTimestamp } from '../../utils/format';
import { LayoutDashboard, LineChart, BookOpen, Activity, RefreshCw } from 'lucide-react';

export default function Sidebar() {
  const { refreshKey, refresh } = useRefresh();
  const { data: signalsData } = useApi(() => api.signalsToday(), [refreshKey]);
  const { data: healthData } = useApi(() => api.health());

  const [scanning, setScanning] = React.useState(false);
  const [scanResult, setScanResult] = React.useState(null);

  React.useEffect(() => {
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

  const navItems = [
    { to: "/", icon: <LayoutDashboard size={18} />, label: "Dashboard", end: true },
    { to: "/backtest", icon: <LineChart size={18} />, label: "Backtest" },
    { to: "/journal", icon: <BookOpen size={18} />, label: "Journal" },
  ];

  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 ${
      isActive
        ? 'bg-green-500/10 text-green-400 font-medium shadow-[0_0_10px_rgba(34,197,94,0.1)_inset]'
        : 'text-[--text-muted] hover:bg-white/5 hover:text-[--text-secondary]'
    }`;

  return (
    <aside className="flex flex-col h-full bg-[--bg-card]/80 backdrop-blur-md overflow-hidden">
      {/* Logo Area */}
      <div className="h-16 flex items-center px-6 border-b border-[--glass-border] shrink-0">
        <span className="font-bold text-base md:text-lg tracking-tight text-green-400 flex items-center gap-2 overflow-hidden whitespace-nowrap" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          <Activity size={20} className={healthData?.status === 'ok' ? 'animate-pulse-dot flex-shrink-0' : 'flex-shrink-0'} />
          <span className="truncate">SIGNAL RADAR</span>
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 flex flex-col gap-2 overflow-y-auto overflow-x-hidden">
        {navItems.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
            {item.icon}
            <span className="truncate">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Action Area (Bottom) */}
      <div className="p-4 border-t border-[--glass-border] space-y-4 shrink-0">
        <div className="text-[10px] text-[--text-muted] px-2 truncate">
          {signalsData?.scanner_timestamp ? (
            <span>Last scan: {formatTimestamp(signalsData.scanner_timestamp)}</span>
          ) : (
            <span>Ready to scan</span>
          )}
        </div>

        {scanResult && scanResult.status === 'error' && (
          <div className="text-xs text-red-400 px-2 truncate">{scanResult.detail || 'Scan failed'}</div>
        )}

        <div className="flex gap-2">
           <button
              onClick={runScanner}
              disabled={scanning}
              className={`flex-1 flex justify-center items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all duration-300 cursor-pointer relative overflow-hidden ${
                scanning
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                  : 'bg-green-500/10 text-green-400 border border-green-500/30 hover:bg-green-500/20 hover:border-green-500/50 shadow-[0_0_15px_rgba(34,197,94,0.15)]'
              }`}
            >
              {scanning && <span className="absolute inset-0 animate-shimmer" />}
              <span className="relative z-10 flex items-center gap-2 overflow-hidden">
                {scanning ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
                <span className="truncate">{scanning ? 'Wait...' : 'Scanner'}</span>
              </span>
            </button>

            <button
              onClick={refresh}
              className="p-2 rounded-lg border border-[--glass-border] text-[--text-secondary] hover:bg-white/5 hover:text-[--text-primary] transition-colors cursor-pointer flex items-center justify-center bg-[--bg-primary]"
              title="Refresh Data"
            >
              <RefreshCw size={14} />
            </button>
        </div>
      </div>
      
       {/* Status Bar Replacement */}
       <div className="h-8 border-t border-[--glass-border] bg-[--bg-primary] flex items-center justify-between px-4 text-[10px] text-[--text-muted] shrink-0">
          <span className="truncate">v1.0</span>
          <span className="flex items-center gap-1.5 shrink-0">
            <span className={`w-1.5 h-1.5 rounded-full ${healthData?.status === 'ok' ? 'bg-green-500' : 'bg-red-500'}`} />
            API
          </span>
       </div>
    </aside>
  );
}
