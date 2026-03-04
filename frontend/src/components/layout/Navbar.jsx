import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';
import { formatTimestamp } from '../../utils/format';
import { LayoutDashboard, LineChart, BookOpen, Activity, RefreshCw, HelpCircle, GraduationCap } from 'lucide-react';
import GuideModal from './GuideModal';

export default function Navbar() {
  const { refreshKey, refresh } = useRefresh();
  const { data: signalsData } = useApi(() => api.signalsToday(), [refreshKey]);
  const { data: healthData } = useApi(() => api.health());

  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [isGuideOpen, setIsGuideOpen] = useState(false);

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
    { to: "/strategies", icon: <GraduationCap size={18} />, label: "Stratégies" },
    { to: "/backtest", icon: <LineChart size={18} />, label: "Backtest" },
    { to: "/journal", icon: <BookOpen size={18} />, label: "Journal" },
  ];

  const linkClass = ({ isActive }) =>
    `flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all duration-200 ${
      isActive
        ? 'bg-green-500/10 text-green-400 font-medium'
        : 'text-[--text-muted] hover:bg-white/5 hover:text-[--text-secondary]'
    }`;

  return (
    <>
      <header className="h-16 flex items-center justify-between px-6 bg-[--bg-card]/80 backdrop-blur-md border-b border-[--glass-border] sticky top-0 z-50">
        {/* Logo Area */}
        <div className="flex items-center shrink-0">
          <span className="font-bold text-lg tracking-tight text-green-400 flex items-center gap-2" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            <Activity size={20} className={healthData?.status === 'ok' ? 'animate-pulse-dot flex-shrink-0' : 'flex-shrink-0'} />
            <span className="hidden xs:inline">SIGNAL RADAR</span>
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex items-center gap-1 mx-4">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
              {item.icon}
              <span className="hidden sm:inline">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Action Area */}
        <div className="flex items-center gap-2 md:gap-4 shrink-0">
          <div className="hidden md:flex flex-col text-right">
            <div className="text-[10px] text-[--text-muted]">
              {signalsData?.scanner_timestamp ? (
                <span>Last scan: {formatTimestamp(signalsData.scanner_timestamp)}</span>
              ) : (
                <span>Ready to scan</span>
              )}
            </div>
            {scanResult && scanResult.status === 'error' && (
              <div className="text-[10px] text-red-400">{scanResult.detail || 'Scan failed'}</div>
            )}
          </div>

          <div className="flex gap-2">
             <button
                onClick={() => setIsGuideOpen(true)}
                className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-300 cursor-pointer bg-white/5 text-[--text-muted] hover:text-white hover:bg-white/10 border border-transparent hover:border-white/10"
                title="Aide Rapide"
              >
                <HelpCircle size={16} />
                <span>Aide</span>
              </button>

             <button
                onClick={runScanner}
                disabled={scanning}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-300 cursor-pointer relative overflow-hidden ${
                  scanning
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                    : 'bg-green-500/10 text-green-400 border border-green-500/30 hover:bg-green-500/20 hover:border-green-500/50'
                }`}
              >
                {scanning ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
                <span className="hidden sm:inline">{scanning ? 'Wait...' : 'Scanner'}</span>
              </button>

              <button
                onClick={refresh}
                className="p-1.5 rounded-lg border border-[--glass-border] text-[--text-secondary] hover:bg-white/5 hover:text-[--text-primary] transition-colors cursor-pointer flex items-center justify-center bg-[--bg-primary]"
                title="Refresh Data"
              >
                <RefreshCw size={14} />
              </button>
          </div>

          {/* Status indicator */}
          <div className="flex items-center gap-1.5 ml-1 md:ml-2 md:pl-4 border-l border-[--glass-border]">
             <span className={`w-1.5 h-1.5 rounded-full ${healthData?.status === 'ok' ? 'bg-green-500' : 'bg-red-500'}`} />
             <span className="text-[10px] text-[--text-muted] hidden lg:inline uppercase tracking-widest">v1.0</span>
          </div>
        </div>
      </header>

      <GuideModal isOpen={isGuideOpen} onClose={() => setIsGuideOpen(false)} />
    </>
  );
}
