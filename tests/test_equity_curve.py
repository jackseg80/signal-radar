from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)

def test_get_equity_curve_ok():
    # Requires production_params.yaml to have META in rsi2 universe
    response = client.get("/api/backtest/equity-curve?strategy=rsi2&symbol=META")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "META"
    assert data["strategy"] == "rsi2"
    assert "equity_curve" in data
    assert "trades" in data
    assert len(data["equity_curve"]) > 0
    assert data["n_trades"] == len(data["trades"])

def test_get_equity_curve_404_symbol():
    response = client.get("/api/backtest/equity-curve?strategy=rsi2&symbol=INVALID_SYM")
    assert response.status_code == 404

def test_get_equity_curve_404_strategy():
    response = client.get("/api/backtest/equity-curve?strategy=invalid_strat&symbol=META")
    assert response.status_code == 404
