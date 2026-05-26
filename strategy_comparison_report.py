import sys
import os

# Add package directory to path to ensure clean imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from DiscordAlertsTrader.strategy_analyzer import run_backtests_and_optimizations

if __name__ == "__main__":
    print("="*80)
    print("   DISCORD ALERTS TRADER - EXIT STRATEGIES BACKTEST & OPTIMIZATION ENGINE")
    print("="*80)
    print("This script will scan 1,178 closed trades, optimize Stop-Loss/Trailing-Stop parameters,")
    print("and evaluate 4 virtual exit portfolios against the original trader performance.")
    print("Running simulations...\n")
    
    run_backtests_and_optimizations()
    
    print("\nSimulations completed. Virtual portfolios are stored in your data/ directory:")
    print("  - data/strat_trim_portfolio.csv")
    print("  - data/strat_mae_stop_portfolio.csv")
    print("  - data/strat_fixed_ts_portfolio.csv")
    print("  - data/strat_atr_ts_portfolio.csv")
    print("  - data/strategy_comparison.csv (summary data)")
    print("="*80)
