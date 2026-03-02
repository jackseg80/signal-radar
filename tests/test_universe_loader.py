"""Tests pour le chargement des univers YAML."""

from __future__ import annotations

import pytest

from config.universe_loader import UniverseConfig, list_universes, load_universe


class TestLoadUniverse:
    """Tests de chargement d'un univers YAML."""

    def test_load_universe_us_stocks(self) -> None:
        """Charge us_stocks_large.yaml avec succes."""
        config = load_universe("us_stocks_large")
        assert isinstance(config, UniverseConfig)
        assert config.name == "US Large Cap Stocks"
        assert config.market == "us_stocks"
        assert len(config.assets) > 30

    def test_load_universe_default_start(self) -> None:
        """Assets sans start explicite utilisent default_start."""
        config = load_universe("us_etfs_broad")
        assert config.assets["SPY"] == "2005-01-01"
        assert config.assets["QQQ"] == "2005-01-01"

    def test_load_universe_custom_start(self) -> None:
        """META a un start custom."""
        config = load_universe("us_stocks_large")
        assert config.assets["META"] == "2012-06-01"
        assert config.assets["MSFT"] == "2005-01-01"

    def test_load_universe_not_found(self) -> None:
        """FileNotFoundError pour un univers inexistant."""
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_universe("nonexistent")

    def test_list_universes(self) -> None:
        """list_universes retourne au moins les 4 fichiers crees."""
        universes = list_universes()
        assert isinstance(universes, list)
        assert "us_stocks_large" in universes
        assert "us_etfs_broad" in universes
        assert "us_etfs_sector" in universes
        assert "forex_majors" in universes

    def test_universe_config_fields(self) -> None:
        """Tous les champs de UniverseConfig sont presents."""
        config = load_universe("us_etfs_sector")
        assert config.name == "US Sector ETFs"
        assert config.description != ""
        assert config.market == "us_etfs"
        assert config.default_fee_model == "us_etfs_usd_account"
        assert config.default_start == "2005-01-01"

    def test_load_universe_forex(self) -> None:
        """Tickers forex avec =X sont charges correctement."""
        config = load_universe("forex_majors")
        assert "EURUSD=X" in config.assets
        assert "GBPUSD=X" in config.assets
        assert config.default_fee_model == "forex_saxo"
        assert len(config.assets) == 7

    def test_load_universe_etfs_sector(self) -> None:
        """11 sector ETFs charges."""
        config = load_universe("us_etfs_sector")
        assert len(config.assets) == 11
        assert "XLK" in config.assets
        assert config.assets["XLRE"] == "2015-10-01"
        assert config.assets["XLC"] == "2018-06-01"
