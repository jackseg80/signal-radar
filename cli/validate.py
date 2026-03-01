"""CLI pour valider une stratégie.

Usage:
    python -m cli.validate rsi2_stocks
    python -m cli.validate rsi2_etfs
"""

from __future__ import annotations

import sys

from engine.fee_model import FEE_MODEL_US_ETFS_USD, FEE_MODEL_US_STOCKS_USD
from strategies.rsi2_mean_reversion import RSI2MeanReversion
from validation.config import ValidationConfig
from validation.pipeline import validate
from validation.report import print_report

# ── Univers prédéfinis ──

UNIVERSE_STOCKS: dict[str, str] = {
    "META": "2012-06-01",
    "MSFT": "2005-01-01",
    "GOOGL": "2005-01-01",
    "NVDA": "2005-01-01",
    "AMZN": "2005-01-01",
    "GS": "2005-01-01",
}

UNIVERSE_ETFS: dict[str, str] = {
    "SPY": "2005-01-01",
    "QQQ": "2005-01-01",
    "IWM": "2005-01-01",
    "DIA": "2005-01-01",
    "EFA": "2005-01-01",
}

# ── Presets ──

PRESETS: dict[str, tuple] = {
    "rsi2_stocks": (
        RSI2MeanReversion,
        ValidationConfig(
            universe=UNIVERSE_STOCKS,
            data_end="2025-01-01",
            is_end="2014-01-01",
            initial_capital=10_000.0,
            whole_shares=True,
            slippage_pct=0.0003,
            fee_model=FEE_MODEL_US_STOCKS_USD,
            oos_mid="2019-07-01",
        ),
    ),
    "rsi2_etfs": (
        RSI2MeanReversion,
        ValidationConfig(
            universe=UNIVERSE_ETFS,
            data_end="2025-01-01",
            is_end="2014-01-01",
            initial_capital=100_000.0,
            whole_shares=False,
            slippage_pct=0.0003,
            fee_model=FEE_MODEL_US_ETFS_USD,
            oos_mid="2019-07-01",
        ),
    ),
}


def main() -> None:
    """Entry point."""
    if len(sys.argv) < 2 or sys.argv[1] not in PRESETS:
        print("Usage: python -m cli.validate <preset>")
        print(f"Presets: {', '.join(PRESETS.keys())}")
        sys.exit(1)

    preset_name = sys.argv[1]
    strategy_cls, vconfig = PRESETS[preset_name]
    strategy = strategy_cls()

    print(f"\n  Pipeline de validation : {strategy.name} / {preset_name}")
    print(f"  Capital={vconfig.initial_capital:,.0f}, "
          f"whole_shares={vconfig.whole_shares}, "
          f"OOS={vconfig.is_end} -> {vconfig.data_end}\n")

    report = validate(strategy, vconfig)
    print_report(report)


if __name__ == "__main__":
    main()
