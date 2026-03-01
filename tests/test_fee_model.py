"""Tests pour le FeeModel."""

from engine.fee_model import (
    FEE_MODEL_EU_STOCKS,
    FEE_MODEL_FOREX,
    FEE_MODEL_US_STOCKS,
    FeeModel,
)


class TestFeeModel:
    def test_us_stocks_entry_cost(self):
        """US stocks : $1 commission + spread/2 + fx_conversion."""
        fm = FEE_MODEL_US_STOCKS
        notional = 10_000.0
        cost = fm.total_entry_cost(notional)
        # $1 + 10000*0.0005/2 + 10000*0.0025 + 10000*0 (tax)
        expected = 1.0 + 10_000 * 0.00025 + 10_000 * 0.0025
        assert abs(cost - expected) < 0.01

    def test_us_stocks_exit_cost_no_tax(self):
        """US stocks exit : pas de tax à la sortie."""
        fm = FEE_MODEL_US_STOCKS
        notional = 10_000.0
        cost = fm.total_exit_cost(notional)
        # $1 + spread/2 + fx_conversion (pas de tax)
        expected = 1.0 + 10_000 * 0.00025 + 10_000 * 0.0025
        assert abs(cost - expected) < 0.01

    def test_forex_no_commission(self):
        """Forex : pas de commission, seulement le spread."""
        fm = FEE_MODEL_FOREX
        notional = 100_000.0
        cost = fm.total_entry_cost(notional)
        # spread/2 uniquement = 100000 * 0.0001 / 2 = 5.0
        expected = 100_000 * 0.0001 / 2
        assert abs(cost - expected) < 0.01

    def test_overnight_cost_scales_with_days(self):
        """Le coût overnight augmente avec la durée de détention."""
        fm = FeeModel(overnight_daily_pct=0.0001)  # 0.01% par jour
        notional = 50_000.0
        cost_1 = fm.overnight_cost(notional, 1)
        cost_10 = fm.overnight_cost(notional, 10)
        assert abs(cost_10 - cost_1 * 10) < 0.001

    def test_overnight_zero_for_stocks(self):
        """Stocks cash : pas de financement overnight."""
        fm = FEE_MODEL_US_STOCKS
        cost = fm.overnight_cost(100_000.0, 30)
        assert cost == 0.0

    def test_eu_stocks_includes_tax(self):
        """EU stocks : la taxe est incluse à l'entrée."""
        fm = FEE_MODEL_EU_STOCKS
        notional = 10_000.0
        entry = fm.total_entry_cost(notional)
        exit_ = fm.total_exit_cost(notional)
        # Entry inclut tax (0.3%), exit non
        assert entry > exit_
        tax_diff = entry - exit_
        expected_tax = 10_000 * 0.003
        assert abs(tax_diff - expected_tax) < 0.01

    def test_fee_model_affects_pnl(self):
        """Un trade rentable brut peut être perdant net avec les frais."""
        from engine.fast_backtest import _close_trend_position

        fm = FeeModel(
            commission_per_trade=5.0,
            spread_pct=0.002,
            fx_conversion_pct=0.003,
        )
        # Trade LONG : entry=100, exit=101 (+1%), qty=100
        entry_notional = 100 * 100
        entry_fee = fm.total_entry_cost(entry_notional)
        pnl = _close_trend_position(
            direction=1, entry_price=100.0, exit_price=101.0,
            quantity=100.0, fee_model=fm, entry_fee=entry_fee,
            n_holding_days=0,
        )
        # Gross PnL = (101-100)*100 = $100
        # Entry cost = $5 + 10000*0.002/2 + 10000*0.003 = $5 + $10 + $30 = $45
        # Exit cost = $5 + 10100*0.002/2 + 10100*0.003 = $5 + $10.1 + $30.3 = $45.4
        # Net PnL ≈ 100 - 45 - 45.4 ≈ $9.6 (still positive but much reduced)
        assert pnl < 100.0  # Fees reduce the PnL
        assert pnl > 0      # But still positive with these params
