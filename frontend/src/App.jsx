import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { RefreshProvider } from './hooks/useRefresh.jsx';
import Navbar from './components/layout/Navbar';
import StatusBar from './components/layout/StatusBar';
import Dashboard from './pages/Dashboard';
import Backtest from './pages/Backtest';
import Journal from './pages/Journal';

export default function App() {
  return (
    <RefreshProvider>
      <BrowserRouter>
        <div className="flex flex-col min-h-screen">
          <Navbar />
          <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/backtest" element={<Backtest />} />
              <Route path="/journal" element={<Journal />} />
            </Routes>
          </main>
          <StatusBar />
        </div>
      </BrowserRouter>
    </RefreshProvider>
  );
}
