"""Analyse comparative : IBS+TOM vs TOM pur.

Compare les screens TOM et IBS+TOM sur les memes univers pour evaluer
si le filtre IBS ameliore l'edge TOM.

Usage:
    python scripts/compare_ibs_tom.py

Sortie : docs/ANALYSIS_IBS_TOM.md
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Ajouter la racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.runner import run_screen, ScreenResult

UNIVERSES = ["us_stocks_large", "us_etfs_broad"]

# Seuil pour les categories de comparaison
PF_WINNER_THRESHOLD = 0.10
PF_LOSER_THRESHOLD = 0.10

# Seuil minimum de trades pour la fiabilite statistique
MIN_TRADES_FOR_RELIABILITY = 20


# ── Analyse ──────────────────────────────────────────────────────────────────


def _by_symbol(result: ScreenResult) -> dict[str, dict]:
    """Indexe les resultats par symbole."""
    return {a["symbol"]: a for a in result.assets}


def compare_universe(universe: str) -> dict:
    """Run TOM + IBS+TOM sur un univers et calcule les metriques comparatives."""
    print(f"  [tom] {universe}...")
    tom_result = run_screen("tom", universe)

    print(f"  [ibs_tom] {universe}...")
    ibs_result = run_screen("ibs_tom", universe)

    tom_by_sym = _by_symbol(tom_result)
    ibs_by_sym = _by_symbol(ibs_result)

    # Assets presents dans les deux strategies
    common_symbols = set(tom_by_sym) & set(ibs_by_sym)
    tom_only = set(tom_by_sym) - set(ibs_by_sym)

    per_asset: list[dict] = []

    for sym in sorted(common_symbols):
        t = tom_by_sym[sym]
        b = ibs_by_sym[sym]

        trade_reduction = (
            (t["n_trades"] - b["n_trades"]) / t["n_trades"] * 100
            if t["n_trades"] > 0 else 0.0
        )
        pf_delta = b["profit_factor"] - t["profit_factor"]
        wr_delta = b["win_rate"] - t["win_rate"]
        sharpe_delta = b["sharpe"] - t["sharpe"]

        if pf_delta > PF_WINNER_THRESHOLD:
            category = "WINNER"
        elif pf_delta < -PF_LOSER_THRESHOLD:
            category = "LOSER"
        else:
            category = "NEUTRAL"

        reliable = b["n_trades"] >= MIN_TRADES_FOR_RELIABILITY

        per_asset.append({
            "symbol": sym,
            "tom_trades": t["n_trades"],
            "tom_wr": t["win_rate"],
            "tom_pf": t["profit_factor"],
            "tom_sharpe": t["sharpe"],
            "ibs_tom_trades": b["n_trades"],
            "ibs_tom_wr": b["win_rate"],
            "ibs_tom_pf": b["profit_factor"],
            "ibs_tom_sharpe": b["sharpe"],
            "trade_reduction_pct": trade_reduction,
            "pf_delta": pf_delta,
            "wr_delta": wr_delta,
            "sharpe_delta": sharpe_delta,
            "category": category,
            "reliable": reliable,
        })

    # Assets TOM sans signal IBS (0 trades ibs_tom)
    tom_only_assets = [tom_by_sym[s] for s in sorted(tom_only)]

    # Metriques agregees
    n_assets = len(per_asset)
    n_winner = sum(1 for a in per_asset if a["category"] == "WINNER")
    n_loser = sum(1 for a in per_asset if a["category"] == "LOSER")
    n_neutral = sum(1 for a in per_asset if a["category"] == "NEUTRAL")
    n_reliable = sum(1 for a in per_asset if a["reliable"])

    tom_total_trades = sum(a["tom_trades"] for a in per_asset)
    ibs_total_trades = sum(a["ibs_tom_trades"] for a in per_asset)

    avg_pf_delta = (
        sum(a["pf_delta"] for a in per_asset) / n_assets if n_assets > 0 else 0.0
    )
    avg_wr_delta = (
        sum(a["wr_delta"] for a in per_asset) / n_assets if n_assets > 0 else 0.0
    )
    avg_sharpe_delta = (
        sum(a["sharpe_delta"] for a in per_asset) / n_assets if n_assets > 0 else 0.0
    )

    pf_deltas_sorted = sorted(a["pf_delta"] for a in per_asset)
    median_pf_delta = (
        pf_deltas_sorted[n_assets // 2] if n_assets > 0 else 0.0
    )

    # Moyennes ponderees par n_trades pour la "vue pooled"
    if tom_total_trades > 0:
        tom_avg_wr = (
            sum(a["tom_wr"] * a["tom_trades"] for a in per_asset) / tom_total_trades
        )
        tom_avg_pf = (
            sum(a["tom_pf"] * a["tom_trades"] for a in per_asset) / tom_total_trades
        )
    else:
        tom_avg_wr = tom_avg_pf = 0.0

    if ibs_total_trades > 0:
        ibs_avg_wr = (
            sum(a["ibs_tom_wr"] * a["ibs_tom_trades"] for a in per_asset)
            / ibs_total_trades
        )
        ibs_avg_pf = (
            sum(a["ibs_tom_pf"] * a["ibs_tom_trades"] for a in per_asset)
            / ibs_total_trades
        )
    else:
        ibs_avg_wr = ibs_avg_pf = 0.0

    trade_reduction_pct = (
        (tom_total_trades - ibs_total_trades) / tom_total_trades * 100
        if tom_total_trades > 0 else 0.0
    )

    return {
        "universe": universe,
        "per_asset": per_asset,
        "tom_only_assets": tom_only_assets,
        "n_assets": n_assets,
        "n_winner": n_winner,
        "n_loser": n_loser,
        "n_neutral": n_neutral,
        "n_reliable": n_reliable,
        "tom_total_trades": tom_total_trades,
        "ibs_total_trades": ibs_total_trades,
        "trade_reduction_pct": trade_reduction_pct,
        "tom_avg_wr": tom_avg_wr,
        "tom_avg_pf": tom_avg_pf,
        "ibs_avg_wr": ibs_avg_wr,
        "ibs_avg_pf": ibs_avg_pf,
        "avg_pf_delta": avg_pf_delta,
        "avg_wr_delta": avg_wr_delta,
        "avg_sharpe_delta": avg_sharpe_delta,
        "median_pf_delta": median_pf_delta,
    }


# ── Rapport Markdown ──────────────────────────────────────────────────────────


def _fmt_pf(v: float) -> str:
    return f"{v:.2f}"


def _fmt_wr(v: float) -> str:
    return f"{v:.1f}%"


def _fmt_sharpe(v: float) -> str:
    return f"{v:.2f}"


def _fmt_delta(v: float, prefix: str = "+") -> str:
    if v > 0:
        return f"+{v:.2f}"
    return f"{v:.2f}"


def _category_section(per_asset: list[dict], category: str, label: str) -> str:
    assets = [a for a in per_asset if a["category"] == category]
    if not assets:
        return f"**{label} (0 assets)**\n\nAucun asset dans cette categorie.\n"

    lines = [
        f"**{label} ({len(assets)} assets)**",
        "",
        "| Asset | TOM Trades | TOM PF | IBS+TOM Trades | IBS+TOM PF | Delta PF | WR delta | Reliable |",
        "|-------|-----------|--------|----------------|------------|----------|----------|----------|",
    ]
    for a in sorted(assets, key=lambda x: x["pf_delta"], reverse=True):
        reliable = "yes" if a["reliable"] else "no (*)"
        lines.append(
            f"| {a['symbol']} "
            f"| {a['tom_trades']} "
            f"| {_fmt_pf(a['tom_pf'])} "
            f"| {a['ibs_tom_trades']} "
            f"| {_fmt_pf(a['ibs_tom_pf'])} "
            f"| {_fmt_delta(a['pf_delta'])} "
            f"| {_fmt_delta(a['wr_delta'])}% "
            f"| {reliable} |"
        )
    return "\n".join(lines)


def _universe_section(comp: dict) -> str:
    u = comp["universe"]
    sections = [
        f"## Resultats : {u}",
        "",
        "### Vue d'ensemble",
        "",
        "| Metrique | TOM pur | IBS+TOM | Delta |",
        "|----------|---------|---------|-------|",
        f"| Trades (total) | {comp['tom_total_trades']} | {comp['ibs_total_trades']} | {_fmt_delta(-comp['trade_reduction_pct'])}% |",
        f"| PF (pond. trades) | {_fmt_pf(comp['tom_avg_pf'])} | {_fmt_pf(comp['ibs_avg_pf'])} | {_fmt_delta(comp['ibs_avg_pf'] - comp['tom_avg_pf'])} |",
        f"| WR (pond. trades) | {_fmt_wr(comp['tom_avg_wr'])} | {_fmt_wr(comp['ibs_avg_wr'])} | {_fmt_delta(comp['ibs_avg_wr'] - comp['tom_avg_wr'])}% |",
        f"| PF delta moyen | - | - | {_fmt_delta(comp['avg_pf_delta'])} |",
        f"| PF delta median | - | - | {_fmt_delta(comp['median_pf_delta'])} |",
        f"| Sharpe delta moyen | - | - | {_fmt_delta(comp['avg_sharpe_delta'])} |",
        "",
        f"Assets analyses : {comp['n_assets']} (communs aux deux strategies)",
        f"Assets fiables (>= {MIN_TRADES_FOR_RELIABILITY} trades IBS+TOM) : {comp['n_reliable']}/{comp['n_assets']}",
        f"Reduction de trades moyenne : {comp['trade_reduction_pct']:.1f}%",
        "",
        "### Resultats par categorie",
        "",
        _category_section(comp["per_asset"], "WINNER", f"Winners (PF delta > +{PF_WINNER_THRESHOLD:.2f})"),
        "",
        _category_section(comp["per_asset"], "NEUTRAL", f"Neutral (|PF delta| <= {PF_WINNER_THRESHOLD:.2f})"),
        "",
        _category_section(comp["per_asset"], "LOSER", f"Losers (PF delta < -{PF_LOSER_THRESHOLD:.2f})"),
    ]

    if comp["tom_only_assets"]:
        sections.append("")
        sections.append(
            f"### Assets TOM sans trades IBS+TOM ({len(comp['tom_only_assets'])} assets)\n"
        )
        no_trade_syms = [a["symbol"] for a in comp["tom_only_assets"]]
        sections.append(", ".join(no_trade_syms))

    return "\n".join(sections)


def generate_report(comparisons: list[dict]) -> str:
    today = date.today().isoformat()

    # Analyse globale
    total_winner = sum(c["n_winner"] for c in comparisons)
    total_loser = sum(c["n_loser"] for c in comparisons)
    total_neutral = sum(c["n_neutral"] for c in comparisons)
    total_assets = sum(c["n_assets"] for c in comparisons)
    total_reliable = sum(c["n_reliable"] for c in comparisons)

    avg_pf_delta_global = (
        sum(c["avg_pf_delta"] * c["n_assets"] for c in comparisons) / total_assets
        if total_assets > 0 else 0.0
    )

    avg_trade_reduction = (
        sum(c["trade_reduction_pct"] for c in comparisons) / len(comparisons)
    )

    # Conclusion basee sur les donnees
    if avg_pf_delta_global > 0.05 and total_winner > total_loser and total_reliable >= total_assets * 0.6:
        conclusion = (
            "Le filtre IBS ameliore le PF moyen et produit plus de Winners que de Losers. "
            "L'hypothese est confirmee. Envisager l'ajout au scanner si les resultats "
            "de validation complete sont consistants."
        )
        recommandation = (
            "Lancer `python -m cli.validate ibs_tom us_stocks_large` pour la validation complete "
            "(robustesse 18 combos + stabilite sous-periodes + t-test). "
            "Si VALIDATED sur >= 3 assets majeurs, ajouter au scanner en remplacement de TOM pur."
        )
    elif total_reliable < total_assets * 0.5:
        conclusion = (
            "Le filtre IBS est trop restrictif : moins de la moitie des assets ont "
            f">= {MIN_TRADES_FOR_RELIABILITY} trades. Les resultats sont statistiquement peu fiables. "
            "Relacher le seuil (ibs_entry_threshold=0.3) ou abandonner la combinaison."
        )
        recommandation = (
            "Modifier `ibs_entry_threshold` a 0.3 dans les default_params et relancer. "
            "Alternativement, tester uniquement sur les assets ou TOM a deja un PF > 1.3."
        )
    else:
        conclusion = (
            "Les resultats sont mitiges : le filtre IBS n'ameliore pas systematiquement le PF TOM. "
            "L'hypothese n'est pas confirmee sur cet univers."
        )
        recommandation = (
            "Garder ibs_tom en recherche sans l'ajouter au scanner. "
            "Explorer d'autres filtres d'entree (ex: RSI2 < 20 en fin de mois)."
        )

    lines = [
        "# Analyse comparative : IBS + Turn of Month vs Turn of Month pur",
        "",
        f"Date : {today}",
        "Periode OOS : 2014-01-01 a aujourd'hui",
        "Capital : $10,000 (stocks whole shares), $100,000 (ETFs fractional)",
        "Fee model : us_stocks_usd_account / us_etfs_usd_account",
        "",
        "## Resume",
        "",
        conclusion,
        "",
        "## Hypothese testee",
        "",
        "Les meilleurs trades TOM arrivent quand le marche est oversold en fin de mois (IBS < 0.2).",
        "Le filtre IBS devrait eliminer les entrees sur des jours haussiers qui diluent l'edge.",
        "Attendu : moins de trades, mais win rate et PF plus eleves.",
        "",
        "**Params IBS+TOM :** entry_days_before_eom=5, ibs_entry_threshold=0.2, sma_trend_period=200,",
        "exit_day_of_new_month=3, ibs_exit_threshold=0.8",
        "",
        "## Synthese globale",
        "",
        f"| | Valeur |",
        f"|--|--|",
        f"| Assets analyses | {total_assets} |",
        f"| Assets fiables (>= {MIN_TRADES_FOR_RELIABILITY} trades IBS+TOM) | {total_reliable}/{total_assets} |",
        f"| Winners (PF ameliore > +{PF_WINNER_THRESHOLD:.2f}) | {total_winner} |",
        f"| Neutral | {total_neutral} |",
        f"| Losers (PF degrade > -{PF_LOSER_THRESHOLD:.2f}) | {total_loser} |",
        f"| PF delta moyen (global) | {_fmt_delta(avg_pf_delta_global)} |",
        f"| Reduction trades moyenne | {avg_trade_reduction:.1f}% |",
        "",
    ]

    for comp in comparisons:
        lines.append(_universe_section(comp))
        lines.append("")

    lines.extend([
        "## Analyse",
        "",
        "### 1. Le filtre IBS ameliore-t-il le PF ?",
        "",
        f"PF delta moyen global : {_fmt_delta(avg_pf_delta_global)}.",
        f"Winners : {total_winner}, Losers : {total_loser}, Neutral : {total_neutral}.",
        "",
        "### 2. Le gain compense-t-il la perte de trades ?",
        "",
        f"Reduction moyenne de trades : {avg_trade_reduction:.1f}%.",
        f"Assets avec >= {MIN_TRADES_FOR_RELIABILITY} trades IBS+TOM : {total_reliable}/{total_assets}.",
        "Un asset avec < 20 trades OOS n'est pas statistiquement exploitable.",
        "",
        "### 3. Le filtre est-il trop restrictif ?",
        "",
        f"IBS < 0.2 filtre ~80% des entrees TOM. Si trade_reduction > 60%, la plupart des assets",
        f"passent sous le seuil de fiabilite statistique.",
        "",
        "## Conclusion",
        "",
        conclusion,
        "",
        "## Recommandation",
        "",
        recommandation,
    ])

    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    print("Compare IBS+TOM vs TOM pur")
    print("=" * 40)

    comparisons = []
    for universe in UNIVERSES:
        print(f"\nUnivers : {universe}")
        comp = compare_universe(universe)
        comparisons.append(comp)

        print(
            f"  Winners: {comp['n_winner']}, "
            f"Losers: {comp['n_loser']}, "
            f"Neutral: {comp['n_neutral']}"
        )
        print(
            f"  PF delta moyen: {comp['avg_pf_delta']:+.2f}, "
            f"Trade reduction: {comp['trade_reduction_pct']:.1f}%"
        )
        print(f"  Assets fiables: {comp['n_reliable']}/{comp['n_assets']}")

    report = generate_report(comparisons)

    out_path = Path(__file__).parent.parent / "docs" / "ANALYSIS_IBS_TOM.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"\nRapport sauvegarde : {out_path}")


if __name__ == "__main__":
    main()
