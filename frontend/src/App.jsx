import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { RefreshProvider } from './hooks/useRefresh.jsx';
import { ToastProvider } from './hooks/useToasts.jsx';
import Navbar from './components/layout/Navbar';
import Dashboard from './pages/Dashboard';
import Backtest from './pages/Backtest';
import Journal from './pages/Journal';
import Strategies from './pages/Strategies';

export default function App() {
  return (
    <ToastProvider>
      <RefreshProvider>
        <BrowserRouter>
          <div className="flex flex-col min-h-screen bg-[--bg-primary] text-[--text-primary]">
            <Navbar />
            
            <main className="flex-1 min-w-0 relative z-0">
              <div className="max-w-[1600px] mx-auto p-4 md:p-6 lg:p-8 xl:p-10">
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/backtest" element={<Backtest />} />
                  <Route path="/journal" element={<Journal />} />
                  <Route path="/strategies" element={<Strategies />} />
                </Routes>
              </div>
            </main>
          </div>
        </BrowserRouter>
      </RefreshProvider>
    </ToastProvider>
  );
}
