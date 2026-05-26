import os
import sys
import glob
import pandas as pd
import numpy as np
from datetime import timedelta

# Ensure python can import from the package root directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.strategy_analyzer import (
    run_trim_strategy,
    run_mae_strategy,
    run_fixed_ts_strategy,
    run_atr_ts_strategy
)

def run_trader_specific_optimization():
    data_dir = os.path.join(cfg['root']['dir'], '..', 'data')
    portfolio_source = os.path.join(data_dir, 'analysts_portfolio_bulltrades_5-10_8-8.csv')
    
    if not os.path.exists(portfolio_source):
        print(f"Error: Source portfolio not found at {portfolio_source}")
        return
        
    full_df = pd.read_csv(portfolio_source)
    closed_full = full_df[full_df['isOpen'] == 0]
    
    # Identify unique traders and filter out those with fewer than 5 trades for statistical relevance
    trader_counts = closed_full['Trader'].value_counts()
    active_traders = trader_counts[trader_counts >= 5].index.tolist()
    
    print("=" * 80)
    print(f"RUNNING INDIVIDUAL TRADER STRATEGY SWEEPS ({len(active_traders)} active analysts)")
    print("=" * 80)
    
    # Load messages for Strategy 1
    msg_files = glob.glob(os.path.join(data_dir, "*_message_history.csv"))
    combined_msgs = []
    for f in msg_files:
        try:
            m_df = pd.read_csv(f)
            if 'Content' in m_df.columns and 'Author' in m_df.columns and 'Date' in m_df.columns:
                combined_msgs.append(m_df)
        except Exception:
            pass
    if combined_msgs:
        all_msgs = pd.concat(combined_msgs, ignore_index=True)
    else:
        all_msgs = pd.DataFrame(columns=['Author', 'Content', 'Date'])
        
    results = []
    temp_csv_path = os.path.join(data_dir, 'temp_trader_portfolio.csv')
    
    for trader in active_traders:
        print(f"\nOptimizing exits for: {trader} ({trader_counts[trader]} closed trades)...")
        
        # Filter full portfolio for only this trader
        trader_full_df = full_df[full_df['Trader'] == trader].copy()
        trader_full_df.to_csv(temp_csv_path, index=False)
        
        best_pnl = -float('inf')
        best_strategy_name = "Original STC"
        best_param = "None"
        best_win_rate = 0.0
        best_profit_factor = "N/A"
        
        # --- Evaluate Original STC ---
        trader_closed = trader_full_df[trader_full_df['isOpen'] == 0]
        pnl_col = 'PnL$' if 'PnL$' in trader_closed.columns else 'PnL$-actual'
        original_pnl = trader_closed[pnl_col].sum()
        original_wins = trader_closed[trader_closed[pnl_col] > 0]
        original_win_rate = len(original_wins) / len(trader_closed) * 100
        gross_prof = original_wins[pnl_col].sum()
        gross_loss = abs(trader_closed[trader_closed[pnl_col] <= 0][pnl_col].sum())
        original_pf = gross_prof / gross_loss if gross_loss > 0 else float('inf')
        
        if original_pnl > best_pnl:
            best_pnl = original_pnl
            best_strategy_name = "Original STC"
            best_param = "None"
            best_win_rate = original_win_rate
            best_profit_factor = original_pf
            
        # --- Sweep Strategy 1: Trim Detector ---
        try:
            strat1_df = run_trim_strategy(temp_csv_path, all_msgs)
            strat1_closed = strat1_df[strat1_df['isOpen'] == 0]
            s1_pnl = strat1_closed['PnL$'].sum()
            s1_wins = strat1_closed[strat1_closed['PnL$'] > 0]
            s1_win_rate = len(s1_wins) / len(strat1_closed) * 100
            s1_gp = s1_wins['PnL$'].sum()
            s1_gl = abs(strat1_closed[strat1_closed['PnL$'] <= 0]['PnL$'].sum())
            s1_pf = s1_gp / s1_gl if s1_gl > 0 else float('inf')
            
            if s1_pnl > best_pnl:
                best_pnl = s1_pnl
                best_strategy_name = "Strategy 1 (Trim Detector)"
                best_param = "Parsed Messages"
                best_win_rate = s1_win_rate
                best_profit_factor = s1_pf
        except Exception as e:
            print(f"  Error running Strategy 1 for {trader}: {e}")
            
        # --- Sweep Strategy 2: MAE Stop Loss ---
        for mult in [1.0, 1.25, 1.5, 2.0, 2.5]:
            try:
                strat2_df = run_mae_strategy(temp_csv_path, multiplier=mult)
                strat2_closed = strat2_df[strat2_df['isOpen'] == 0]
                s2_pnl = strat2_closed['PnL$'].sum()
                s2_wins = strat2_closed[strat2_closed['PnL$'] > 0]
                s2_win_rate = len(s2_wins) / len(strat2_closed) * 100
                s2_gp = s2_wins['PnL$'].sum()
                s2_gl = abs(strat2_closed[strat2_closed['PnL$'] <= 0]['PnL$'].sum())
                s2_pf = s2_gp / s2_gl if s2_gl > 0 else float('inf')
                
                if s2_pnl > best_pnl:
                    best_pnl = s2_pnl
                    best_strategy_name = "Strategy 2 (Optimized MAE Stop)"
                    best_param = f"{mult}x MAE"
                    best_win_rate = s2_win_rate
                    best_profit_factor = s2_pf
            except Exception as e:
                pass
                
        # --- Sweep Strategy 3: Fixed Trailing Stop ---
        for pct in [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0, 60.0, 70.0]:
            try:
                strat3_df = run_fixed_ts_strategy(temp_csv_path, ts_pct=pct)
                strat3_closed = strat3_df[strat3_df['isOpen'] == 0]
                s3_pnl = strat3_closed['PnL$'].sum()
                s3_wins = strat3_closed[strat3_closed['PnL$'] > 0]
                s3_win_rate = len(s3_wins) / len(strat3_closed) * 100
                s3_gp = s3_wins['PnL$'].sum()
                s3_gl = abs(strat3_closed[strat3_closed['PnL$'] <= 0]['PnL$'].sum())
                s3_pf = s3_gp / s3_gl if s3_gl > 0 else float('inf')
                
                if s3_pnl > best_pnl:
                    best_pnl = s3_pnl
                    best_strategy_name = "Strategy 3 (Optimized Fixed TS)"
                    best_param = f"{pct}% TS"
                    best_win_rate = s3_win_rate
                    best_profit_factor = s3_pf
            except Exception as e:
                pass
                
        # --- Sweep Strategy 4: Dynamic ATR Trailing Stop ---
        for n in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            try:
                strat4_df = run_atr_ts_strategy(temp_csv_path, n_atr=n)
                strat4_closed = strat4_df[strat4_df['isOpen'] == 0]
                s4_pnl = strat4_closed['PnL$'].sum()
                s4_wins = strat4_closed[strat4_closed['PnL$'] > 0]
                s4_win_rate = len(s4_wins) / len(strat4_closed) * 100
                s4_gp = s4_wins['PnL$'].sum()
                s4_gl = abs(strat4_closed[strat4_closed['PnL$'] <= 0]['PnL$'].sum())
                s4_pf = s4_gp / s4_gl if s4_gl > 0 else float('inf')
                
                if s4_pnl > best_pnl:
                    best_pnl = s4_pnl
                    best_strategy_name = "Strategy 4 (Optimized ATR TS)"
                    best_param = f"{n}x ATR"
                    best_win_rate = s4_win_rate
                    best_profit_factor = s4_pf
            except Exception as e:
                pass
                
        # Register best strategy details for this trader
        results.append({
            "Trader": trader,
            "Total Trades": trader_counts[trader],
            "Original Profit $": round(original_pnl, 2),
            "Original Win Rate %": round(original_win_rate, 2),
            "Optimal Strategy": best_strategy_name,
            "Optimal Parameter": best_param,
            "Optimal Profit $": round(best_pnl, 2),
            "Optimal Win Rate %": round(best_win_rate, 2),
            "Profit Factor": round(best_profit_factor, 2) if not np.isinf(best_profit_factor) else "N/A"
        })
        
        print(f"  --> Best Strategy: {best_strategy_name} ({best_param}) | Profit: ${best_pnl:,.2f} | Win Rate: {best_win_rate:.1f}%")
        
    # Clean up temp file
    if os.path.exists(temp_csv_path):
        os.remove(temp_csv_path)
        
    # Save the report
    res_df = pd.DataFrame(results)
    report_path = os.path.join(data_dir, 'trader_optimal_strategies.csv')
    res_df.to_csv(report_path, index=False)
    
    print("\n" + "=" * 90)
    print(f"{'INDIVIDUAL TRADER OPTIMAL STRATEGY REPORT':^90}")
    print("=" * 90)
    print(f"{'Trader':<20} | {'Trades':<6} | {'Orig Profit':<11} | {'Best Profit':<11} | {'Optimal Strategy':<30}")
    print("-" * 90)
    for _, row in res_df.iterrows():
        print(f"{row['Trader']:<20} | {row['Total Trades']:<6} | ${row['Original Profit $']:<10,.2f} | ${row['Optimal Profit $']:<10,.2f} | {row['Optimal Strategy']} ({row['Optimal Parameter']})")
    print("=" * 90)
    print(f"Full trader-specific exit strategy report saved to: {report_path}")

if __name__ == "__main__":
    run_trader_specific_optimization()
