# signal-radar

Swing trading signal engine for stocks and forex. Daily trend following with gap-aware backtest engine.

## Quick start

```bash
pip install -e ".[dev]"
pytest tests/ -v
python scripts/optimize.py --strategy donchian --symbol AAPL
```
