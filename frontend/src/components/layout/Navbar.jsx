import { NavLink } from 'react-router-dom';
import { useRefresh } from '../../hooks/useRefresh.jsx';
import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';
import { formatTimestamp } from '../../utils/format';

export default function Navbar() {
  const { refreshKey, refresh } = useRefresh();
  const { data } = useApi(() => api.signalsToday(), [refreshKey]);

  const linkClass = ({ isActive }) =>
    `px-3 py-1.5 rounded text-sm transition-colors ${
      isActive
        ? 'bg-white/10 text-[--text-primary] font-medium'
        : 'text-[--text-muted] hover:text-[--text-secondary]'
    }`;

  return (
    <header className="border-b border-[--border-subtle] bg-[--bg-card]">
      <div className="max-w-7xl mx-auto px-4 flex items-center h-12 gap-6">
        <span className="font-bold text-base tracking-tight text-green-400" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
          SIGNAL RADAR
        </span>

        <nav className="flex gap-1">
          <NavLink to="/" className={linkClass} end>Dashboard</NavLink>
          <NavLink to="/backtest" className={linkClass}>Backtest</NavLink>
        </nav>

        <div className="ml-auto flex items-center gap-4 text-xs text-[--text-muted]">
          {data?.scanner_timestamp && (
            <span>Last scan: {formatTimestamp(data.scanner_timestamp)}</span>
          )}
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
