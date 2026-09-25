import test from 'node:test';
import assert from 'node:assert/strict';
import { groupBuySignals } from '../src/components/signals/groupBuySignals.js';

test('all technical stock buys stay visible despite paper or cash gates', () => {
  const groups = groupBuySignals({
    rsi2: { signals: [{ symbol: 'META', technical_signal: 'BUY', paper_status: 'BLOCKED', eligibility: 'BLOCKED', score: -0.01 }] },
    ibs: { signals: [{ symbol: 'META', technical_signal: 'BUY', paper_status: 'MERGED', eligibility: 'BLOCKED', score: 0.02 }] },
    tom: { signals: [{ symbol: 'AAPL', technical_signal: 'HOLD', paper_status: 'HOLD' }] },
  });
  assert.equal(groups.length, 1);
  assert.equal(groups[0].symbol, 'META');
  assert.deepEqual(groups[0].rows.map((row) => row.strategy), ['ibs', 'rsi2']);
});
