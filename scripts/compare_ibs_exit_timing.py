"""Compare IBS exit at close[i] vs open[i+1] to quantify directional bias.

Post-processes existing backtest trades: same entry decisions, same exit
decisions, only the exit PRICE changes (close[i] -> open[i+1]).

This isolates the directional bias of IBS > 0.8 exit (close near high)
without modifying the simulator engine.
"""

from __future__ import annotations

import pandas as pd

from data.base_loader import to_cache_arrays
from data.yahoo_loader import YahooLoader
from engine.backtest_config import BacktestConfig
from engine.fee_model import FEE_MODEL_US_STOCKS_USD
from engine.indicator_cache import build_cache
from engine.simulator import simulate
from engine.types import TradeResult
from strategies.ibs_mean_reversion import IBSMeanReversion


# IBS validated assets (Phase 3 results)
ASSETS: dict[str, str] = {
    "META": "2004-01-01",
    "MSFT": "2004-01-01",
    "GOOGL": "2004-08-01",
    "NVDA": "2004-01-01",
    "AMZN": "2004-01-01",
    "AAPL": "2004-01-01",
}

OOS_START = "2014-01-01"
DATA_END = "2025-12-31"

# Close-based exit reasons (all IBS exits use close[i])
CLOSE_EXIT_REASONS = {"ibs_exit", "prev_high_exit", "trend_break"}


def _merge_grid_with_defaults(strategy: IBSMeanReversion) -> dict[str, list]:
    """Merge param_grid + default_params for cache coverage."""
    grid = dict(strategy.param_grid())
    defaults = strategy.default_params()
    for key, value in defaults.items():
        if "period" in key and key not in grid and isinstance(value, (int, float)):
            grid[key] = [int(value)]
    return grid


def _adjusted_pnl(
    trade: TradeResult,
    new_exit_price: float,
    config: BacktestConfig,
    extra_holding_days: int = 1,
) -> float:
    """Recalculate PnL with a different exit price."""
    gross_pnl = trade.direction * (new_exit_price - trade.entry_price) * trade.quantity
    exit_notional = new_exit_price * trade.quantity
    exit_fee = config.fee_model.total_exit_cost(exit_notional)
    entry_notional = trade.entry_price * trade.quantity
    overnight = config.fee_model.overnight_cost(
        entry_notional, trade.holding_days + extra_holding_days,
    )
    return gross_pnl - trade.entry_fee - exit_fee - overnight


def _metrics(pnls: list[float]) -> tuple[int, float, float, float]:
    """Compute (n_trades, win_rate, profit_factor, total_pnl)."""
    n = len(pnls)
    if n == 0:
        return 0, 0.0, 0.0, 0.0
    winners = sum(1 for p in pnls if p > 0)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p <= 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    wr = winners / n
    return n, wr, pf, sum(pnls)


def main() -> None:
    strategy = IBSMeanReversion()
    loader = YahooLoader()
    params = strategy.default_params()
    cache_grid = _merge_grid_with_defaults(strategy)

    results: list[dict] = []
    # Per exit-reason breakdown
    reason_deltas: dict[str, list[float]] = {r: [] for r in CLOSE_EXIT_REASONS}

    for symbol, start_date in ASSETS.items():
        print(f"  {symbol}...", end=" ", flush=True)

        df = loader.get_daily_candles(symbol, start_date, DATA_END)

        oos_start_idx = int(df.index.searchsorted(pd.Timestamp(OOS_START)))
        warmup = strategy.warmup(params)
        if oos_start_idx < warmup:
            oos_start_idx = warmup

        arrays = to_cache_arrays(df)
        dates = df.index.values
        cache = build_cache(arrays, cache_grid, dates=dates)

        config = BacktestConfig(
            symbol=symbol,
            initial_capital=10_000.0,
            slippage_pct=0.0003,
            fee_model=FEE_MODEL_US_STOCKS_USD,
            whole_shares=True,
        )

        result = simulate(strategy, cache, params, config, start_idx=oos_start_idx)

        # Post-process: replace close-based exits with open[i+1]
        original_pnls: list[float] = []
        adjusted_pnls: list[float] = []
        n_close_exits = 0

        for trade in result.trades:
            original_pnls.append(trade.pnl)

            if (
                trade.exit_reason in CLOSE_EXIT_REASONS
                and trade.exit_candle + 1 < cache.n_candles
            ):
                n_close_exits += 1
                new_exit_price = cache.opens[trade.exit_candle + 1]
                new_pnl = _adjusted_pnl(trade, new_exit_price, config)
                adjusted_pnls.append(new_pnl)

                # Track per-reason delta
                delta = new_pnl - trade.pnl
                reason_deltas[trade.exit_reason].append(delta)
            else:
                adjusted_pnls.append(trade.pnl)

        n_orig, wr_orig, pf_orig, total_orig = _metrics(original_pnls)
        _, wr_adj, pf_adj, total_adj = _metrics(adjusted_pnls)

        pf_delta = (pf_adj - pf_orig) / pf_orig * 100 if pf_orig > 0 else 0.0

        results.append({
            "symbol": symbol,
            "trades": n_orig,
            "close_exits": n_close_exits,
            "pf_close": pf_orig,
            "pf_open": pf_adj,
            "pf_delta_pct": pf_delta,
            "wr_close": wr_orig,
            "wr_open": wr_adj,
            "total_close": total_orig,
            "total_open": total_adj,
        })
        print(f"{n_orig} trades, PF {pf_orig:.2f} -> {pf_adj:.2f} ({pf_delta:+.1f}%)")

    # ── Summary table ──
    sep = "=" * 100
    print(f"\n{sep}")
    print("  IBS Mean Reversion -- Exit close[i] vs open[i+1] comparison")
    print("  OOS 2014-2025, $10k whole shares, fee_model=us_stocks_usd_account")
    print(sep)

    header = (
        f"  {'Symbol':<8} {'Trades':>6} {'Close%':>7}"
        f"  {'PF close':>8} {'PF open':>8} {'Delta':>7}"
        f"  {'WR close':>8} {'WR open':>8}"
        f"  {'PnL close':>10} {'PnL open':>10}"
    )
    print(header)
    print("  " + "-" * 96)

    for r in results:
        close_pct = r["close_exits"] / r["trades"] * 100 if r["trades"] > 0 else 0
        print(
            f"  {r['symbol']:<8} {r['trades']:>6} {close_pct:>6.0f}%"
            f"  {r['pf_close']:>8.2f} {r['pf_open']:>8.2f} {r['pf_delta_pct']:>+6.1f}%"
            f"  {r['wr_close']:>7.0%} {r['wr_open']:>7.0%}"
            f"  ${r['total_close']:>9.2f} ${r['total_open']:>9.2f}"
        )

    # ── Pooled summary ──
    total_pnl_close = sum(r["total_close"] for r in results)
    total_pnl_open = sum(r["total_open"] for r in results)
    avg_pf_close = sum(r["pf_close"] for r in results) / len(results)
    avg_pf_open = sum(r["pf_open"] for r in results) / len(results)

    print("  " + "-" * 96)
    print(
        f"  {'AVG/TOT':<8} {'':>6} {'':>7}"
        f"  {avg_pf_close:>8.2f} {avg_pf_open:>8.2f}"
        f" {(avg_pf_open - avg_pf_close) / avg_pf_close * 100:>+6.1f}%"
        f"  {'':>8} {'':>8}"
        f"  ${total_pnl_close:>9.2f} ${total_pnl_open:>9.2f}"
    )

    delta_total = total_pnl_open - total_pnl_close
    delta_pct = delta_total / total_pnl_close * 100 if total_pnl_close != 0 else 0
    print(f"\n  PnL total delta: ${delta_total:>+.2f} ({delta_pct:>+.1f}%)")

    # ── Breakdown by exit reason ──
    print(f"\n  Breakdown by exit reason:")
    print(f"  {'Reason':<20} {'Count':>6} {'Avg delta':>10} {'Total delta':>12}")
    print("  " + "-" * 52)
    for reason in CLOSE_EXIT_REASONS:
        deltas = reason_deltas[reason]
        if deltas:
            avg_d = sum(deltas) / len(deltas)
            tot_d = sum(deltas)
            print(f"  {reason:<20} {len(deltas):>6} ${avg_d:>+9.2f} ${tot_d:>+11.2f}")
        else:
            print(f"  {reason:<20} {0:>6} {'N/A':>10} {'N/A':>12}")

    print(sep)


if __name__ == "__main__":
    main()
