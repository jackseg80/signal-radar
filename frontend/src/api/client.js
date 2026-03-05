const API_BASE = '/api';

async function fetchJson(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, options);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || res.statusText);
  }
  return res.json();
}

/**
 * Filter out null, undefined and empty strings from params
 * to avoid sending them to the backend which expects true nulls.
 */
function buildQueryString(params = {}) {
  const cleanParams = {};
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== 'undefined') {
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
  signalsToday: (strategy) => fetchJson(`/signals/today${buildQueryString({ strategy })}`),
  signalsHistory: (params = {}) => fetchJson(`/signals/history${buildQueryString(params)}`),
  scannerRun: () => fetchJson('/scanner/run', { method: 'POST' }),
  scannerStatus: () => fetchJson('/scanner/status'),
  
  // Market & Assets
  marketOverview: () => fetchJson('/market/overview'),
  assetDetails: (symbol) => fetchJson(`/market/asset/${symbol}`),
  assetHistory: (symbol, days = 60) => fetchJson(`/market/asset/${symbol}/history?days=${days}`),
  assetPrices: (symbol, days = 60) => fetchJson(`/market/asset/${symbol}/prices?days=${days}`),

  // Positions & Trades
  openPositions: (strategy) => fetchJson(`/positions/open${buildQueryString({ strategy })}`),
  closedTrades: (params = {}) => fetchJson(`/positions/closed${buildQueryString(params)}`),
  
  // Performance
  performanceSummary: () => fetchJson('/performance/summary'),
  equityCurve: () => fetchJson('/performance/equity-curve'),
  
  // Backtest
  screens: (params = {}) => fetchJson(`/backtest/screens${buildQueryString(params)}`),
  validations: (params = {}) => fetchJson(`/backtest/validations${buildQueryString(params)}`),
  compare: (params = {}) => fetchJson(`/backtest/compare${buildQueryString(params)}`),
  backtestEquityCurve: (strategy, symbol) =>
    fetchJson(`/backtest/equity-curve${buildQueryString({ strategy, symbol })}`),
  backtestRobustness: (strategy, symbol, universe) => 
    fetchJson(`/backtest/robustness${buildQueryString({ strategy, symbol, universe })}`),
  
  // Live Trades
  liveOpen: (data) => fetchJson(`/live/open${buildQueryString(data)}`, { method: 'POST' }),
  liveClose: (data) => fetchJson(`/live/close${buildQueryString(data)}`, { method: 'POST' }),
  liveDelete: (id) => fetchJson(`/live/${id}`, { method: 'DELETE' }),
  liveActive: (strategy) => fetchJson(`/live/open${buildQueryString({ strategy })}`),
  liveClosed: (params = {}) => fetchJson(`/live/closed${buildQueryString(params)}`),
  liveSummary: () => fetchJson('/live/summary'),
  liveCompare: () => fetchJson('/live/compare'),

  // Journal
  journalEntries: (params = {}) => fetchJson(`/journal/entries${buildQueryString(params)}`),
  journalUpdatePaper: (id, data) => fetchJson(`/journal/paper/${id}/update`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }),
  journalUpdateLive: (id, data) => fetchJson(`/journal/live/${id}/update`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }),
  journalPaperNote: (id, notes) => patchJson(`/journal/paper/${id}/notes`, { notes }),
  journalLiveNote: (id, notes) => patchJson(`/journal/live/${id}/notes`, { notes }),

  // Config
  getSettings: () => fetchJson('/config/settings'),

  // Health
  health: () => fetchJson('/health')
};
