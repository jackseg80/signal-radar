// -- Number formatting --

export function formatPrice(n) {
  if (n == null || isNaN(n)) return '--';
  return `$${Number(n).toFixed(2)}`;
}

export function formatPnl(n) {
  if (n == null || isNaN(n)) return '--';
  const v = Number(n);
  const sign = v >= 0 ? '+' : '';
  return `${sign}$${Math.abs(v).toFixed(2)}`;
}

export function formatPct(n) {
  if (n == null || isNaN(n)) return '--';
  const v = Number(n);
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

export function formatPF(n) {
  if (n == null || isNaN(n)) return '--';
  return Number(n).toFixed(2);
}

export function formatDate(s) {
  if (!s) return '--';
  return new Date(s).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

export function formatTimestamp(ts) {
  if (!ts) return '--';
  const d = new Date(ts.replace(' ', 'T'));
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export function pnlColor(n) {
  if (n > 0) return 'text-green-400';
  if (n < 0) return 'text-red-400';
  return 'text-[--text-secondary]';
}

// -- Strategy constants --

const _COLORS_RSI2 = { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500' };
const _COLORS_IBS  = { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500' };
const _COLORS_TOM  = { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500' };

export const STRATEGY_COLORS = {
  rsi2: _COLORS_RSI2,
  ibs:  _COLORS_IBS,
  tom:  _COLORS_TOM,
  // Long-form keys from validations DB
  rsi2_mean_reversion: _COLORS_RSI2,
  ibs_mean_reversion:  _COLORS_IBS,
  turn_of_month:       _COLORS_TOM,
};

export const STRATEGY_LABELS = {
  rsi2: 'RSI(2)',
  ibs: 'IBS',
  tom: 'TOM',
  // Long-form keys from validations DB
  rsi2_mean_reversion: 'RSI(2)',
  ibs_mean_reversion: 'IBS',
  turn_of_month: 'TOM',
};

// -- Signal constants --

export const SIGNAL_COLORS = {
  BUY:             { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-l-green-500' },
  SELL:            { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-l-red-500' },
  SAFETY_EXIT:     { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-l-red-500' },
  HOLD:            { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-l-blue-500' },
  WATCH:           { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-l-amber-500' },
  PENDING_VALID:   { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-l-amber-500' },
  PENDING_EXPIRED: { bg: 'bg-white/5', text: 'text-[--text-muted]', border: 'border-l-[--border-subtle]' },
  NO_SIGNAL:       { bg: 'bg-white/5', text: 'text-[--text-muted]', border: 'border-l-[--border-subtle]' },
};

// -- Verdict constants --

export const VERDICT_COLORS = {
  VALIDATED:   { bg: 'bg-green-500/20', text: 'text-green-400' },
  CONDITIONAL: { bg: 'bg-amber-500/20', text: 'text-amber-400' },
  REJECTED:    { bg: 'bg-red-500/20', text: 'text-red-400' },
};

// Signal sort priority (BUY/SELL first)
const SIGNAL_ORDER = {
  BUY: 0, SELL: 1, SAFETY_EXIT: 2, WATCH: 3, PENDING_VALID: 4,
  HOLD: 5, PENDING_EXPIRED: 6, NO_SIGNAL: 7,
};

export function sortSignals(signals) {
  return [...signals].sort(
    (a, b) => (SIGNAL_ORDER[a.signal] ?? 9) - (SIGNAL_ORDER[b.signal] ?? 9)
  );
}

// -- Heatmap helpers --

export function heatColor(value, min, max, scale = 'diverging') {
  if (value == null || isNaN(value) || min === max) return 'transparent';
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  if (scale === 'diverging') {
    if (t < 0.5) {
      const s = t / 0.5;
      return `rgba(239, 68, 68, ${(0.25 * (1 - s)).toFixed(3)})`;
    }
    const s = (t - 0.5) / 0.5;
    return `rgba(34, 197, 94, ${(0.25 * s).toFixed(3)})`;
  }
  return `rgba(34, 197, 94, ${(0.3 * t).toFixed(3)})`;
}

export function pnlBarWidth(value, maxAbsValue) {
  if (value == null || isNaN(value) || maxAbsValue === 0) return 0;
  return Math.min(100, Math.abs(value) / maxAbsValue * 100);
}
