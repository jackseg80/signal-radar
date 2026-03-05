/**
 * Centralized strategy metadata and mappings for the frontend.
 */

export const STRATEGY_MAPPING = {
  'rsi2': 'rsi2_mean_reversion',
  'ibs': 'ibs_mean_reversion',
  'tom': 'turn_of_month'
};

export const REVERSE_STRATEGY_MAPPING = Object.entries(STRATEGY_MAPPING).reduce((acc, [key, value]) => {
  acc[value] = key;
  return acc;
}, {});

/**
 * Resolves a strategy name (potentially long) to its short canonical key.
 */
export function resolveStrategyKey(name) {
  if (!name) return null;
  const lower = name.toLowerCase();
  if (STRATEGY_MAPPING[lower]) return lower;
  if (REVERSE_STRATEGY_MAPPING[lower]) return REVERSE_STRATEGY_MAPPING[lower];
  
  // Fuzzy match
  if (lower.includes('rsi2')) return 'rsi2';
  if (lower.includes('ibs')) return 'ibs';
  if (lower.includes('month') || lower.includes('tom')) return 'tom';
  
  return lower;
}
