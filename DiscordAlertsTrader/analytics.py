import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

def calculate_excursions(portfolio_csv):
    """
    Reads the portfolio CSV, finds trades missing MAE/MFE,
    downloads 5m data from yfinance for the trade date,
    calculates MAE/MFE, and saves the CSV.
    """
    df = pd.read_csv(portfolio_csv)
    
    if 'MAE' not in df.columns:
        df['MAE'] = np.nan
    if 'MFE' not in df.columns:
        df['MFE'] = np.nan

    # Process only trades that have a date and don't have MAE/MFE yet
    # For performance, we can skip very old trades or group by date
    today = datetime.now().strftime("%Y-%m-%d")
    
    for idx, row in df.iterrows():
        if pd.notnull(row['MAE']) and pd.notnull(row['MFE']):
            continue
            
        date_str = str(row['Date']).split()[0]
        # Only process trades from the last 7 days to avoid huge API pulls
        # yfinance 5m data is only available for the last 60 days
        try:
            trade_date = datetime.strptime(date_str, "%Y-%m-%d")
            if (datetime.now() - trade_date).days > 7:
                continue
        except:
            continue
            
        sym = row['Symbol']
        # yfinance doesn't natively support options tickers perfectly
        # We approximate using the underlying if it's an option
        is_option = "_" in sym
        underlying = sym.split("_")[0] if is_option else sym
        
        # Format futures for yfinance (e.g. /ES -> ES=F)
        if underlying.startswith('/'):
            underlying = underlying[1:] + "=F"
        elif underlying.startswith('@'):
            underlying = underlying[1:] + "=F"
            
        start_date = trade_date.strftime("%Y-%m-%d")
        end_date = (trade_date + timedelta(days=2)).strftime("%Y-%m-%d")
        
        try:
            # Download 5m data
            ticker = yf.Ticker(underlying)
            hist = ticker.history(start=start_date, end=end_date, interval="5m")
            
            if hist.empty:
                continue
                
            entry_price = float(row['Price']) if pd.notnull(row['Price']) else float(row['Price-alert'])
            
            # Since we only have the underlying data for options, the excursion for options 
            # will be an approximation based on the underlying's movement %.
            # For stocks/futures, we use exact prices.
            
            high = hist['High'].max()
            low = hist['Low'].max() # lowest low
            low = hist['Low'].min()
            
            if row['Type'] == 'BTO':
                mfe_pct = (high - entry_price) / entry_price * 100
                mae_pct = (low - entry_price) / entry_price * 100
            else: # STO
                mfe_pct = (entry_price - low) / entry_price * 100
                mae_pct = (entry_price - high) / entry_price * 100
                
            df.loc[idx, 'MAE'] = round(mae_pct, 2)
            df.loc[idx, 'MFE'] = round(mfe_pct, 2)
            
        except Exception as e:
            print(f"Failed to calculate excursion for {sym}: {e}")
            
    df.to_csv(portfolio_csv, index=False)
    print("Excursion data updated successfully.")

def get_analyst_stats(portfolio_csv):
    """
    Aggregates trade logs to build analyst profiles.
    Returns a dataframe.
    """
    try:
        df = pd.read_csv(portfolio_csv)
    except FileNotFoundError:
        return pd.DataFrame()
        
    stats = []
    traders = df['Trader'].dropna().unique()
    
    for t in traders:
        t_df = df[df['Trader'] == t]
        closed_trades = t_df[t_df['isOpen'] == 0]
        
        total_trades = len(closed_trades)
        if total_trades == 0:
            continue
            
        wins = len(closed_trades[closed_trades['PnL$'].astype(float) > 0])
        win_rate = (wins / total_trades) * 100
        
        avg_pnl = closed_trades['PnL$'].astype(float).mean()
        
        avg_mae = t_df['MAE'].mean() if 'MAE' in t_df.columns else np.nan
        avg_mfe = t_df['MFE'].mean() if 'MFE' in t_df.columns else np.nan
        
        stats.append({
            "Analyst": t,
            "Trades": total_trades,
            "Win %": round(win_rate, 1),
            "Avg PnL$": round(avg_pnl, 2),
            "Avg MAE%": round(avg_mae, 1) if not np.isnan(avg_mae) else "N/A",
            "Avg MFE%": round(avg_mfe, 1) if not np.isnan(avg_mfe) else "N/A"
        })
        
    return pd.DataFrame(stats)

def get_atr(symbol, interval="5m", period="5d"):
    """
    Calculates the current ATR for dynamic trailing stops.
    """
    is_option = "_" in symbol
    underlying = symbol.split("_")[0] if is_option else symbol
    
    if underlying.startswith('/'):
        underlying = underlying[1:] + "=F"
    elif underlying.startswith('@'):
        underlying = underlying[1:] + "=F"
        
    try:
        hist = yf.Ticker(underlying).history(period=period, interval=interval)
        if hist.empty:
            return None
            
        high_low = hist['High'] - hist['Low']
        high_close = np.abs(hist['High'] - hist['Close'].shift())
        low_close = np.abs(hist['Low'] - hist['Close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        
        atr = true_range.rolling(14).mean().iloc[-1]
        return atr
    except Exception as e:
        print(f"ATR calculation failed for {symbol}: {e}")
        return None
