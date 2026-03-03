import { useState, useEffect, useCallback, useRef } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { RefreshProvider } from './hooks/useRefresh.jsx';
import Sidebar from './components/layout/Sidebar';
import Dashboard from './pages/Dashboard';
import Backtest from './pages/Backtest';
import Journal from './pages/Journal';

export default function App() {
  const [sidebarWidth, setSidebarWidth] = useState(
    parseInt(localStorage.getItem('sidebar-width')) || 260
  );
  const isResizing = useRef(false);

  const startResizing = useCallback((e) => {
    e.preventDefault();
    isResizing.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    // Add a temporary overlay to capture mouse events if there are iframes or complex components
    const overlay = document.createElement('div');
    overlay.id = 'resize-overlay';
    overlay.style.position = 'fixed';
    overlay.style.inset = '0';
    overlay.style.zIndex = '9999';
    overlay.style.cursor = 'col-resize';
    document.body.appendChild(overlay);
  }, []);

  const stopResizing = useCallback(() => {
    if (!isResizing.current) return;
    isResizing.current = false;
    document.body.style.cursor = 'default';
    document.body.style.userSelect = 'auto';
    const overlay = document.getElementById('resize-overlay');
    if (overlay) overlay.remove();
    localStorage.setItem('sidebar-width', sidebarWidth);
  }, [sidebarWidth]);

  const resize = useCallback((e) => {
    if (isResizing.current) {
      // Constraints: min 180px, max 50% of window width
      const newWidth = Math.min(Math.max(180, e.clientX), window.innerWidth * 0.5);
      setSidebarWidth(newWidth);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', resize);
    window.addEventListener('mouseup', stopResizing);
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [resize, stopResizing]);

  return (
    <RefreshProvider>
      <BrowserRouter>
        <div className="flex h-screen w-screen bg-[--bg-primary] text-[--text-primary] overflow-hidden">
          {/* Sidebar Area */}
          <div 
            style={{ width: `${sidebarWidth}px` }} 
            className="flex-shrink-0 h-full overflow-hidden border-r border-white/5 bg-[--bg-card]/50"
          >
            <Sidebar />
          </div>

          {/* Draggable Handle - Wider hit area (8px) for better UX */}
          <div
            onMouseDown={startResizing}
            className="w-2 hover:bg-green-500/20 cursor-col-resize transition-all flex items-center justify-center group shrink-0 z-50"
          >
            <div className="w-[1px] h-12 bg-white/10 group-hover:bg-green-400/50 transition-colors" />
          </div>

          {/* Main Content Area */}
          <main className="flex-1 min-w-0 h-full overflow-y-auto overflow-x-hidden bg-[--bg-primary] relative z-0">
            <div className="max-w-[1600px] mx-auto p-4 md:p-6 lg:p-8 xl:p-10">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/backtest" element={<Backtest />} />
                <Route path="/journal" element={<Journal />} />
              </Routes>
            </div>
          </main>
        </div>
      </BrowserRouter>
    </RefreshProvider>
  );
}
