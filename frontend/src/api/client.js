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
  assetDetails: (symbol) => fetchJson(`/market/asset/${symbol}`), // À ajouter au backend
  assetHistory: (symbol, days = 60) => fetchJson(`/market/asset/${symbol}/history?days=${days}`), // À ajouter au backend

  // Positions & Trades
  positionsOpen: () => fetchJson('/positions/open'),
  positionsClosed: () => fetchJson('/positions/closed'),
  
  // Performance
  performanceSummary: () => fetchJson('/performance/summary'),
  equityCurve: () => fetchJson('/performance/equity-curve'),
  
  // Backtest
  backtestScreens: (strategy = '', universe = '') => 
    fetchJson(`/backtest/screens?strategy=${strategy}&universe=${universe}`),
  backtestValidations: (strategy = '', universe = '') => 
    fetchJson(`/backtest/validations?strategy=${strategy}&universe=${universe}`),
  backtestCompare: () => fetchJson('/backtest/compare'),
  
  // Live Trades
  liveOpen: (data) => fetchJson('/live/open', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }),
  liveClose: (id, data) => fetchJson(`/live/close/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }),
  liveActive: () => fetchJson('/live/open'),
  liveClosed: () => fetchJson('/live/closed'),
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
