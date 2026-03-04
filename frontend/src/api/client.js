const API_BASE = '/api';

async function fetchJson(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, options);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || res.statusText);
  }
  return res.json();
}

function buildQueryString(params = {}) {
  const cleanParams = {};
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      cleanParams[key] = value;
    }
  });
  const q = new URLSearchParams(cleanParams).toString();
  return q ? `?${q}` : '';
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
  assetPrices: (symbol, days = 60) => fetchJson(`/market/asset/${symbol}/prices?days=${days}`),

  // Positions & Trades
  openPositions: () => fetchJson('/positions/open'),
  closedTrades: (params = {}) => fetchJson(`/positions/closed${buildQueryString(params)}`),
  
  // Performance
  perfSummary: () => fetchJson('/performance/summary'),
  performanceSummary: () => fetchJson('/performance/summary'),
  equityCurve: () => fetchJson('/performance/equity-curve'),
  
  // Backtest
  screens: (params = {}) => fetchJson(`/backtest/screens${buildQueryString(params)}`),
  validations: (params = {}) => fetchJson(`/backtest/validations${buildQueryString(params)}`),
  compare: () => fetchJson('/backtest/compare'),
  backtestRobustness: (strategy, symbol, universe) => 
    fetchJson(`/backtest/robustness?strategy=${strategy}&symbol=${symbol}&universe=${universe}`),
  
  // Live Trades
  liveOpen: (data) => fetchJson(`/live/open${buildQueryString(data)}`, { method: 'POST' }),
  liveClose: (data) => fetchJson(`/live/close${buildQueryString(data)}`, { method: 'POST' }),
  liveDelete: (id) => fetchJson(`/live/${id}`, { method: 'DELETE' }),
  liveActive: () => fetchJson('/live/open'),
  liveClosed: (params = {}) => fetchJson(`/live/closed${buildQueryString(params)}`),
  liveSummary: () => fetchJson('/live/summary'),
  liveCompare: () => fetchJson('/live/compare'),

  // Journal
  journalEntries: (params = {}) => fetchJson(`/journal/entries${buildQueryString(params)}`),
  journalPaperNote: (id, notes) => patchJson(`/journal/paper/${id}/notes`, { notes }),
  journalLiveNote: (id, notes) => patchJson(`/journal/live/${id}/notes`, { notes }),

  // Health
  health: () => fetchJson('/health')
};
