const API_BASE = '/api';

async function fetchJson(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, options);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || res.statusText);
  }
  return res.json();
}

async function patchJson(url, body) {
  return fetchJson(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

export const api = {
  // Signals & Scanner
  signalsToday: () => fetchJson('/signals/today'),
  signalsHistory: (days = 30) => fetchJson(`/signals/history?days=${days}`),
  scannerRun: () => fetchJson('/scanner/run', { method: 'POST' }),
  scannerStatus: () => fetchJson('/scanner/status'),
  
  // Market & Assets
  marketOverview: () => fetchJson('/market/overview'),
  assetDetails: (symbol) => fetchJson(`/market/asset/${symbol}`),
  assetHistory: (symbol, days = 60) => fetchJson(`/market/asset/${symbol}/history?days=${days}`),

  // Positions & Trades
  openPositions: () => fetchJson('/positions/open'),
  closedTrades: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return fetchJson(`/positions/closed?${q}`);
  },
  
  // Performance
  perfSummary: () => fetchJson('/performance/summary'),
  performanceSummary: () => fetchJson('/performance/summary'),
  equityCurve: () => fetchJson('/performance/equity-curve'),
  
  // Backtest
  screens: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return fetchJson(`/backtest/screens?${q}`);
  },
  validations: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return fetchJson(`/backtest/validations?${q}`);
  },
  backtestRobustness: (strategy, symbol, universe) => 
    fetchJson(`/backtest/robustness?strategy=${strategy}&symbol=${symbol}&universe=${universe}`),
  compare: () => fetchJson('/backtest/compare'),
  
  // Backtest Legacy/AssetModal names
  backtestScreens: (strategy = '', universe = '') => 
    fetchJson(`/backtest/screens?strategy=${strategy}&universe=${universe}`),
  backtestValidations: (strategy = '', universe = '') => 
    fetchJson(`/backtest/validations?strategy=${strategy}&universe=${universe}`),
  backtestCompare: () => fetchJson('/backtest/compare'),
  
  // Live Trades
  liveOpen: (data) => {
    const q = new URLSearchParams(data).toString();
    return fetchJson(`/live/open?${q}`, { method: 'POST' });
  },
  liveClose: (data) => {
    const q = new URLSearchParams(data).toString();
    return fetchJson(`/live/close?${q}`, { method: 'POST' });
  },
  liveDelete: (id) => fetchJson(`/live/${id}`, { method: 'DELETE' }),
  liveActive: () => fetchJson('/live/open'),
  liveClosed: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return fetchJson(`/live/closed?${q}`);
  },
  liveSummary: () => fetchJson('/live/summary'),
  liveCompare: () => fetchJson('/live/compare'),

  // Journal
  journalEntries: (params = {}) => {
    const searchParams = new URLSearchParams(params);
    return fetchJson(`/journal/entries?${searchParams.toString()}`);
  },
  journalPaperNote: (id, notes) => patchJson(`/journal/paper/${id}/notes`, { notes }),
  journalLiveNote: (id, notes) => patchJson(`/journal/live/${id}/notes`, { notes }),

  // Health
  health: () => fetchJson('/health')
};
