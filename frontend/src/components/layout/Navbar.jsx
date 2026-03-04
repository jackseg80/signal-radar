import React, { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { useToasts } from '../../hooks/useToasts.jsx';
import { useApi } from '../../hooks/useApi';
import { useCommandPalette } from './CommandPalette.jsx';
import { api } from '../../api/client';
import { formatTimestamp } from '../../utils/format';
import { formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';
import { LayoutDashboard, LineChart, BookOpen, Activity, RefreshCw, HelpCircle, GraduationCap, Search, Command, Terminal } from 'lucide-react';
import GuideModal from './GuideModal';

export default function Navbar() {
  const { refreshKey, refresh } = useRefresh();
  const { addToast } = useToasts();
  const { toggleSearch } = useCommandPalette();
  const { data: signalsData } = useApi(() => api.signalsToday(), [refreshKey]);
  const { data: healthData } = useApi(() => api.health());

  const [scanning, setScanning] = useState(false);
  const [scanOutput, setScanOutput] = useState([]);
  const [isGuideOpen, setIsGuideOpen] = useState(false);
  const [refreshProgress, setRefreshProgress] = useState(0);
  
  const statusInterval = useRef(null);

  // Auto-refresh progress bar (5 min = 300s)
  useEffect(() => {
    const interval = 300000;
    const step = 1000;
    const timer = setInterval(() => {
      setRefreshProgress(prev => {
        if (prev >= 100) return 0;
        return prev + (step / interval) * 100;
      });
    }, step);
    return () => clearInterval(timer);
  }, [refreshKey]);

  // Poll scanner status if running
  useEffect(() => {
    if (scanning) {
      statusInterval.current = setInterval(async () => {
        try {
          const res = await api.scannerStatus();
          setScanOutput(res.output || []);
          if (!res.running) {
            setScanning(false);
            clearInterval(statusInterval.current);
            if (res.status === 'completed') {
              addToast("Scanner terminé avec succès !");
              refresh();
            } else if (res.status === 'error') {
              addToast("Le scanner a échoué", "error");
            }
          }
        } catch (err) {
          console.error("Failed to poll status", err);
        }
      }, 2000);
    }
    return () => clearInterval(statusInterval.current);
  }, [scanning, addToast, refresh]);

  const runScanner = async () => {
    if (scanning) return;
    try {
      await api.scannerRun();
      setScanning(true);
      setScanOutput(["Initialisation..."]);
      addToast("Scanner démarré", "info");
    } catch (err) {
      addToast(err.message, "error");
    }
  };

  const navItems = [
    { to: "/", icon: <LayoutDashboard size={16} />, label: "Dashboard", end: true },
    { to: "/strategies", icon: <GraduationCap size={16} />, label: "Stratégies" },
    { to: "/backtest", icon: <LineChart size={16} />, label: "Backtest" },
    { to: "/journal", icon: <BookOpen size={16} />, label: "Journal" },
  ];

  const linkClass = ({ isActive }) =>
    `flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-all duration-200 ${
      isActive
        ? 'bg-green-500/10 text-green-400 font-bold'
        : 'text-[--text-muted] hover:bg-white/5 hover:text-[--text-secondary]'
    }`;

  const relativeTime = signalsData?.scanner_timestamp 
    ? formatDistanceToNow(new Date(signalsData.scanner_timestamp), { addSuffix: true, locale: fr })
    : null;

  return (
    <>
      <header className="h-16 flex items-center justify-between px-6 bg-[--bg-card]/80 backdrop-blur-md border-b border-[--glass-border] sticky top-0 z-50">
        {/* Left Area: Logo + Navigation */}
        <div className="flex items-center gap-8">
          <div className="flex items-center shrink-0 mr-4">
            <span className="font-bold text-lg tracking-tight text-green-400 flex items-center gap-2" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              <Activity size={20} className={healthData?.status === 'ok' ? 'animate-pulse-dot flex-shrink-0' : 'flex-shrink-0'} />
              <span className="hidden sm:inline">SIGNAL RADAR</span>
            </span>
          </div>

          <nav className="hidden lg:flex items-center gap-1">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
                {item.icon}
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Right Area: Actions + Search + Status */}
        <div className="flex items-center gap-2 md:gap-4 shrink-0">
          <div className="hidden md:flex flex-col text-right max-w-[180px]">
            {scanning ? (
              <div className="flex items-center gap-2 justify-end">
                <span className="text-[9px] text-amber-400 font-bold animate-pulse truncate">
                  {scanOutput[scanOutput.length - 1] || 'Scanning...'}
                </span>
                <Terminal size={10} className="text-amber-400" />
              </div>
            ) : (
              <div className="text-[10px] text-[--text-muted] flex items-center justify-end gap-2">
                {relativeTime ? <span>Scan : {relativeTime}</span> : <span>Prêt à scanner</span>}
                <div className="w-12 h-0.5 bg-white/5 rounded-full overflow-hidden mt-0.5" title="Prochain auto-refresh">
                  <div className={`h-full bg-blue-500/40 transition-all duration-1000 linear`} style={{ width: `${refreshProgress}%` }} />
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-2">
             <button
                onClick={toggleSearch}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-300 cursor-pointer bg-white/5 text-[--text-muted] hover:text-white hover:bg-white/10 border border-transparent hover:border-white/10"
                title="Recherche Globale (Ctrl+K)"
              >
                <Search size={16} />
                <div className="hidden xl:flex items-center gap-1 text-[10px] opacity-50">
                  <Command size={10} />
                  <span>K</span>
                </div>
              </button>

             <button
                onClick={() => setIsGuideOpen(true)}
                className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-300 cursor-pointer bg-white/5 text-[--text-muted] hover:text-white hover:bg-white/10 border border-transparent hover:border-white/10"
                title="Aide Rapide"
              >
                <HelpCircle size={16} />
                <span className="hidden xl:inline text-xs">Aide</span>
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
                {scanning && <span className="absolute inset-0 animate-shimmer opacity-30" />}
                <span className="relative z-10 flex items-center gap-2">
                  {scanning ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
                  <span className="hidden sm:inline">{scanning ? 'Wait...' : 'Scanner'}</span>
                </span>
              </button>

              <button
                onClick={() => {
                  refresh();
                  setRefreshProgress(0);
                  addToast("Données rafraîchies");
                }}
                className="p-1.5 rounded-lg border border-[--glass-border] text-[--text-secondary] hover:bg-white/5 hover:text-[--text-primary] transition-colors cursor-pointer flex items-center justify-center bg-[--bg-primary]"
                title="Refresh Data"
              >
                <RefreshCw size={14} />
              </button>
          </div>

          {/* Status indicator */}
          <div className="flex items-center gap-1.5 ml-1 md:ml-2 md:pl-4 border-l border-[--glass-border]">
             <span className={`w-1.5 h-1.5 rounded-full ${healthData?.status === 'ok' ? 'bg-green-500' : 'bg-red-500'}`} />
             <span className="text-[10px] text-[--text-muted] hidden lg:inline uppercase tracking-widest">v3.0</span>
          </div>
        </div>
      </header>

      <GuideModal isOpen={isGuideOpen} onClose={() => setIsGuideOpen(false)} />
    </>
  );
}
