"""Tests pour les métadonnées d'assets (noms, logos) et la configuration."""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from data.db import SignalRadarDB
from api.app import app

@pytest.fixture
def db(tmp_path: Path) -> SignalRadarDB:
    """SignalRadarDB avec un fichier temporaire."""
    return SignalRadarDB(db_path=tmp_path / "test_metadata.db")

class TestAssetMetadata:
    """Tests pour save_asset_metadata et get_asset_metadata."""
    
    def test_save_and_get_metadata(self, db: SignalRadarDB):
        db.save_asset_metadata("META", "Meta Platforms, Inc.", "https://logo.com/meta.png")
        meta = db.get_asset_metadata("META")
        assert meta is not None
        assert meta["symbol"] == "META"
        assert meta["name"] == "Meta Platforms, Inc."
        assert meta["logo_url"] == "https://logo.com/meta.png"
        
    def test_update_metadata(self, db: SignalRadarDB):
        db.save_asset_metadata("AAPL", "Apple")
        db.save_asset_metadata("AAPL", "Apple Inc.", "https://logo.com/apple.png")
        aapl = db.get_asset_metadata("AAPL")
        assert aapl is not None
        assert aapl["name"] == "Apple Inc."
        assert aapl["logo_url"] == "https://logo.com/apple.png"

    def test_get_all_metadata(self, db: SignalRadarDB):
        db.save_asset_metadata("MSFT", "Microsoft")
        db.save_asset_metadata("GOOGL", "Alphabet")
        all_meta = db.get_all_metadata()
        assert "MSFT" in all_meta
        assert "GOOGL" in all_meta
        assert all_meta["MSFT"]["name"] == "Microsoft"

class TestConfigAPI:
    """Tests pour le nouveau point de terminaison /api/config/settings."""
    
    def test_get_settings(self):
        client = TestClient(app)
        # Endpoint prefix "/api/config" + router path "/settings"
        response = client.get("/api/config/settings")
        assert response.status_code == 200
        data = response.json()
        assert "initial_capital" in data
        # Check it matches config/production_params.yaml (which is 5000 in this project)
        assert data["initial_capital"] == 5000
