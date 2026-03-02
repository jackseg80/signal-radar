const BASE = '/api';

async function fetchJson(path, params = {}) {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, v);
    }
  });
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export const api = {
  health:         ()       => fetchJson('/health'),
  signalsToday:   (p = {}) => fetchJson('/signals/today', p),
  signalHistory:  (p = {}) => fetchJson('/signals/history', p),
  openPositions:  (p = {}) => fetchJson('/positions/open', p),
  closedTrades:   (p = {}) => fetchJson('/positions/closed', p),
  perfSummary:    ()       => fetchJson('/performance/summary'),
  equityCurve:    (p = {}) => fetchJson('/performance/equity-curve', p),
  marketOverview: ()       => fetchJson('/market/overview'),
  screens:        (p = {}) => fetchJson('/backtest/screens', p),
  validations:    (p = {}) => fetchJson('/backtest/validations', p),
  compare:        (p = {}) => fetchJson('/backtest/compare', p),
};
