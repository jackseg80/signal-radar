import { useApi } from '../../hooks/useApi';
import { api } from '../../api/client';

export default function StatusBar() {
  const { data } = useApi(() => api.health());

  return (
    <footer className="border-t border-[--glass-border] bg-[--glass-bg] backdrop-blur-sm px-4 py-1.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-[--text-muted]">
        <span>Signal Radar v1.0</span>
        <span className="flex items-center gap-2">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              data?.status === 'ok' ? 'bg-green-500 animate-pulse-dot' : 'bg-red-500'
            }`}
          />
          API {data?.status ?? '...'}
        </span>
      </div>
    </footer>
  );
}
