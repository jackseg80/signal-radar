#!/bin/bash
set -e
cd d:/Python/signal-radar

OUTPUT="validation_results/full_validation_$(date +%Y%m%d_%H%M%S).txt"
echo "Output -> $OUTPUT"
export PYTHONIOENCODING=utf-8

{
echo "================================================================"
echo "VALIDATION COMPLETE -- signal-radar"
echo "Date: $(date)"
echo "================================================================"
echo ""

echo "################################################################"
echo "# RSI2 -- us_stocks_large"
echo "################################################################"
python -m cli.validate rsi2 us_stocks_large 2>&1
echo ""

echo "################################################################"
echo "# IBS -- us_stocks_large"
echo "################################################################"
python -m cli.validate ibs us_stocks_large 2>&1
echo ""

echo "################################################################"
echo "# TOM -- us_stocks_large"
echo "################################################################"
python -m cli.validate tom us_stocks_large 2>&1
echo ""

echo "################################################################"
echo "# RSI2 -- us_etfs_broad"
echo "################################################################"
python -m cli.validate rsi2 us_etfs_broad 2>&1
echo ""

echo "################################################################"
echo "# IBS -- us_etfs_broad"
echo "################################################################"
python -m cli.validate ibs us_etfs_broad 2>&1
echo ""

echo "################################################################"
echo "# TOM -- us_etfs_broad"
echo "################################################################"
python -m cli.validate tom us_etfs_broad 2>&1
echo ""

echo "################################################################"
echo "# RSI2 -- us_etfs_sector"
echo "################################################################"
python -m cli.validate rsi2 us_etfs_sector 2>&1
echo ""

echo "################################################################"
echo "# IBS -- us_etfs_sector"
echo "################################################################"
python -m cli.validate ibs us_etfs_sector 2>&1
echo ""

echo "################################################################"
echo "# TOM -- us_etfs_sector"
echo "################################################################"
python -m cli.validate tom us_etfs_sector 2>&1
echo ""

echo "################################################################"
echo "# IBS -- forex_majors"
echo "################################################################"
python -m cli.validate ibs forex_majors 2>&1
echo ""

echo "================================================================"
echo "ANALYSE DES RESULTATS"
echo "================================================================"
echo ""

echo "--- analyze summary ---"
python -m cli.analyze summary 2>&1
echo ""

echo "--- analyze compare us_stocks_large ---"
python -m cli.analyze compare us_stocks_large 2>&1
echo ""

echo "--- analyze compare us_etfs_broad ---"
python -m cli.analyze compare us_etfs_broad 2>&1
echo ""

echo "--- analyze compare us_etfs_sector ---"
python -m cli.analyze compare us_etfs_sector 2>&1
echo ""

for ASSET in META NVDA AAPL MSFT GOOGL AMZN V QQQ SPY; do
  echo "--- analyze asset $ASSET ---"
  python -m cli.analyze asset $ASSET 2>&1
  echo ""
done

echo "================================================================"
echo "DONE: $(date)"
echo "================================================================"

} 2>&1 | tee "$OUTPUT"

echo ""
echo "Fichier complet : $OUTPUT"
