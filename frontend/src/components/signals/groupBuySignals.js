export function groupBuySignals(strategies) {
  const groups = new Map();
  Object.entries(strategies || {}).forEach(([strategy, group]) => {
    (group.signals || []).forEach((signal) => {
      if (signal.technical_signal !== 'BUY') return;
      const rows = groups.get(signal.symbol) || [];
      rows.push({ ...signal, strategy });
      groups.set(signal.symbol, rows);
    });
  });
  return [...groups.entries()].map(([symbol, rows]) => ({
    symbol,
    rows: rows.sort((a, b) => a.strategy.localeCompare(b.strategy)),
  })).sort((a, b) => a.symbol.localeCompare(b.symbol));
}
