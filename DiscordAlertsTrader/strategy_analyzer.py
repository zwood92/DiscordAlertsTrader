import os
import re
import glob
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from .configurator import cfg

# ==========================================
# PART 1: Trim/Screenshot Exit Detection (Strategy 1)
# ==========================================

def detect_exit_signal(msg_content, has_attachments=False):
    """
    Parses message content to detect exit and trim signals.
    Returns: (is_exit, qty_pct, price, is_stop)
    """
    if pd.isna(msg_content) or not msg_content:
        if has_attachments:
            # Empty text with screenshot -> Assume 50% trim conservatively
            return True, 0.50, None, False
        return False, 0.0, None, False
        
    content_lower = str(msg_content).lower()
    
    # 1. Detect stop-loss exit
    stopped_match = re.search(r'\b(stopped|stop|stopped out|stop loss|hit sl|sl hit)\b', content_lower)
    if stopped_match:
        return True, 1.0, None, True
        
    # 2. Detect full exit / close / sell all
    exit_all_match = re.search(r'\b(all out|out all|closed|exit|exit all|sold all|sold everything|took all)\b', content_lower)
    if exit_all_match:
        return True, 1.0, None, False
        
    # 3. Detect partial trims
    trim_match = re.search(r'\b(trim|trimmed|trimming|took profit|took profits|locking profit|locked profit|locked in|partial|scale out|scaling out)\b', content_lower)
    if trim_match:
        qty_pct = 0.25  # default trim qty
        if 'half' in content_lower or '1/2' in content_lower or '50%' in content_lower:
            qty_pct = 0.50
        elif '1/3' in content_lower or '33%' in content_lower:
            qty_pct = 0.33
        elif '1/4' in content_lower or '25%' in content_lower:
            qty_pct = 0.25
        elif '3/4' in content_lower or '75%' in content_lower:
            qty_pct = 0.75
            
        # Try to parse price if mentioned, e.g., `@ 1.50` or `at 1.50`
        price = None
        price_match = re.search(r'(?:@|at)\s*[$]*\s*(\d+(?:\.\d+)?)', content_lower)
        if price_match:
            price = float(price_match.group(1))
            
        return True, qty_pct, price, False
        
    # 4. Check general exits / out
    out_match = re.search(r'\b(out|sold|close|took)\b', content_lower)
    if out_match:
        price = None
        price_match = re.search(r'(?:@|at)\s*[$]*\s*(\d+(?:\.\d+)?)', content_lower)
        if price_match:
            price = float(price_match.group(1))
        return True, 1.0, price, False
        
    return False, 0.0, None, False

# ==========================================
# PART 2: Helper Functions & Excursion Parsers
# ==========================================

def parse_trail_stats(trail_stats_str):
    """
    Extracts MAE (min) and MFE (max) and pre-computed trailing stop results from TrailStats string.
    Returns: (mae_pct, mfe_pct, mae_seconds, mfe_seconds, ts_sims)
    """
    if pd.isna(trail_stats_str) or not isinstance(trail_stats_str, str):
        return None, None, None, None, {}
    
    mae_pct = None
    mfe_pct = None
    mae_seconds = None
    mfe_seconds = None
    ts_sims = {}
    
    parts = trail_stats_str.split('|')
    for part in parts:
        part = part.strip()
        if part.startswith('min,'):
            subparts = part.split(',')
            if len(subparts) >= 2:
                pct_str = subparts[1].replace('%', '')
                try:
                    mae_pct = abs(float(pct_str))
                except ValueError:
                    pass
            # Parse duration offset e.g., 'in 1 days 00:38:34'
            for sub in subparts:
                if 'in ' in sub:
                    mae_seconds = parse_duration(sub.replace('in ', ''))
        elif part.startswith('max,'):
            subparts = part.split(',')
            if len(subparts) >= 2:
                pct_str = subparts[1].replace('%', '')
                try:
                    mfe_pct = abs(float(pct_str))
                except ValueError:
                    pass
            for sub in subparts:
                if 'in ' in sub:
                    mfe_seconds = parse_duration(sub.replace('in ', ''))
        elif 'TS:' in part:
            ts_parts = part.split('TS:')
            for ts_part in ts_parts:
                ts_part = ts_part.strip()
                if not ts_part:
                    continue
                subparts = ts_part.split(',')
                if len(subparts) >= 2:
                    ts_val_str = subparts[0]
                    pct_str = subparts[1].replace('%', '')
                    try:
                        ts_pct = float(ts_val_str) * 100
                        ts_return = float(pct_str)
                        ts_sims[ts_pct] = ts_return
                    except ValueError:
                        pass
    return mae_pct, mfe_pct, mae_seconds, mfe_seconds, ts_sims

def parse_duration(dur_str):
    """
    Parses duration string like '1 days 00:38:34' or '00:34:00' into seconds.
    """
    dur_str = dur_str.strip()
    days = 0
    if 'days' in dur_str or 'day' in dur_str:
        parts = re.split(r'days|day', dur_str)
        try:
            days = int(parts[0].strip())
        except ValueError:
            pass
        dur_str = parts[1].strip()
    
    hms = dur_str.split(':')
    try:
        hours = int(hms[0])
        minutes = int(hms[1])
        seconds = int(hms[2]) if len(hms) > 2 else 0
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds).total_seconds()
    except (ValueError, IndexError):
        return None

_synthetic_quotes_cache = {}
_underlying_daily_cache = {}  # {underlying: df}

def get_underlying_daily_history(underlying, start_str, end_str):
    """
    Retrieves daily stock history, caching it over a broad range to avoid redundant network requests.
    """
    if underlying in _underlying_daily_cache:
        return _underlying_daily_cache[underlying]
        
    ticker = yf.Ticker(underlying)
    # If start_str contains '2023' (which is the backtest range), fetch the entire 2023-04-01 to 2023-09-01 broad range once
    if "2023" in start_str:
        fetch_start = "2023-04-01"
        fetch_end = "2023-09-01"
    else:
        # Otherwise dynamically fetch a broad window around requested trade dates
        try:
            start_dt = pd.to_datetime(start_str)
            end_dt = pd.to_datetime(end_str)
            fetch_start = (start_dt - timedelta(days=30)).strftime("%Y-%m-%d")
            fetch_end = (end_dt + timedelta(days=30)).strftime("%Y-%m-%d")
        except Exception:
            fetch_start = start_str
            fetch_end = end_str
            
    try:
        # We always fetch daily '1d' data as it's cached on yfinance for decades and is extremely fast to download
        hist = ticker.history(start=fetch_start, end=fetch_end, interval="1d")
        _underlying_daily_cache[underlying] = hist
        return hist
    except Exception as e:
        print(f"Error fetching daily history for {underlying}: {e}")
        _underlying_daily_cache[underlying] = pd.DataFrame()
        return pd.DataFrame()

def get_synthetic_option_quotes(symbol, start_date, end_date, option_entry_price, default_delta=0.40):
    """
    Uses underlying historical stocks/ETFs daily quotes from yfinance to construct
    an option price path using the Black-Scholes Delta approximation.
    Immunized against reverse/forward stock splits and price scale mismatches.
    """
    if pd.isna(start_date) or not start_date:
        return None
    if pd.isna(end_date) or not end_date:
        end_date = start_date

    cache_key = (symbol, str(start_date), str(end_date), float(option_entry_price), float(default_delta))
    if cache_key in _synthetic_quotes_cache:
        return _synthetic_quotes_cache[cache_key]

    is_option = "_" in symbol
    underlying = symbol.split("_")[0] if is_option else symbol
    if underlying.startswith('/') or underlying.startswith('@'):
        underlying = underlying[1:] + "=F"
        
    start_dt = pd.to_datetime(start_date, utc=True).tz_localize(None)
    end_dt = pd.to_datetime(end_date, utc=True).tz_localize(None) + timedelta(days=2)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")
    
    # Try to load cached broad daily history first
    hist_daily = get_underlying_daily_history(underlying, start_str, end_str)
    
    hist = pd.DataFrame()
    if not hist_daily.empty:
        # Slices cached dataframe locally in memory
        try:
            # Re-localize index to Tz-naive to prevent matching errors
            hist_naive = hist_daily.copy()
            hist_naive.index = pd.to_datetime(hist_naive.index).tz_localize(None)
            hist = hist_naive.loc[start_str:end_str]
        except Exception:
            pass
            
    if hist.empty:
        # Fallback to dynamic yfinance call
        ticker = yf.Ticker(underlying)
        try:
            hist = ticker.history(start=start_str, end=end_str, interval="1d")
        except Exception as e:
            print(f"Failed to fetch yfinance data for {underlying}: {e}")
            _synthetic_quotes_cache[cache_key] = None
            return None
            
    if hist.empty:
        _synthetic_quotes_cache[cache_key] = None
        return None
        
    hist = hist.reset_index()
    date_col = 'Datetime' if 'Datetime' in hist.columns else 'Date' if 'Date' in hist.columns else hist.columns[0]
    timestamps = pd.to_datetime(hist[date_col]).dt.tz_localize(None).astype('int64') // 10**9
    
    stock_entry_price = hist['Open'].iloc[0]
    quotes_list = []
    
    is_put = False
    if is_option and len(symbol.split("_")) > 1:
        is_put = "P" in symbol.split("_")[1]
    multiplier = -1 if is_put else 1
    
    # Reconstruct the unadjusted stock price at BTO using strike/entry estimates
    strike_estimate = option_entry_price
    if is_option and len(symbol.split("_")) > 1:
        opt_part = symbol.split("_")[1]
        match = re.search(r'[CP](\d+(?:\.\d+)?)', opt_part)
        if match:
            strike_estimate = float(match.group(1))
    else:
        strike_estimate = option_entry_price
        
    for idx, row in hist.iterrows():
        ts = timestamps.iloc[idx]
        stock_high = row['High']
        stock_low = row['Low']
        stock_close = row['Close']
        
        # Calculate percentage price changes of underlying relative to BTO stock price
        # This ratio is invariant to forward/reverse splits!
        dStock_unadjusted = strike_estimate * (stock_close - stock_entry_price) / stock_entry_price
        dStock_high_unadjusted = strike_estimate * ((stock_high if not is_put else stock_low) - stock_entry_price) / stock_entry_price
        dStock_low_unadjusted = strike_estimate * ((stock_low if not is_put else stock_high) - stock_entry_price) / stock_entry_price
        
        if is_option:
            opt_close = option_entry_price + default_delta * multiplier * dStock_unadjusted
            opt_high = option_entry_price + default_delta * multiplier * dStock_high_unadjusted
            opt_low = option_entry_price + default_delta * multiplier * dStock_low_unadjusted
            
            opt_close = max(0.01, opt_close)
            opt_high = max(0.01, opt_high)
            opt_low = max(0.01, opt_low)
        else:
            # For stock, we simply apply the percentage change to option_entry_price
            opt_close = option_entry_price * (stock_close / stock_entry_price)
            opt_high = option_entry_price * (stock_high / stock_entry_price)
            opt_low = option_entry_price * (stock_low / stock_entry_price)
            
        quotes_list.append({
            'timestamp': ts,
            'ask': opt_close,
            'bid': opt_close,
            'last': opt_close,
            'high': opt_high,
            'low': opt_low
        })
        
    res_df = pd.DataFrame(quotes_list)
    _synthetic_quotes_cache[cache_key] = res_df
    return res_df

# ==========================================
# PART 3: Simulation Engines for 4 Strategies
# ==========================================

def run_trim_strategy(portfolio_csv, messages_df):
    """
    Strategy 1: Trim/Screenshot detection strategy.
    Scans analyst message logs to find exit/trim signals.
    """
    df = pd.read_csv(portfolio_csv)
    trim_df = df.copy()
    
    # Pre-parse messages to speed up lookup
    messages_df['Author_clean'] = messages_df['Author'].str.lower().str.split('#').str[0]
    messages_df['Date_parsed'] = pd.to_datetime(messages_df['Date'], utc=True, errors='coerce').dt.tz_localize(None)
    
    for idx, row in trim_df.iterrows():
        if row['isOpen'] == 1:
            continue  # skip currently open trades for backtest simulation
            
        trader_clean = str(row['Trader']).lower().split('#')[0]
        entry_date = pd.to_datetime(row['Date'], utc=True).tz_localize(None)
        stc_date = pd.to_datetime(row['STC-Date'], utc=True).tz_localize(None) if pd.notnull(row['STC-Date']) else (entry_date + timedelta(days=5))
        
        # Find messages from same trader in window
        msk = (messages_df['Author_clean'] == trader_clean) & \
              (messages_df['Date_parsed'] > entry_date) & \
              (messages_df['Date_parsed'] <= stc_date)
              
        trader_msgs = messages_df[msk].sort_values(by='Date_parsed')
        
        position_remaining = 1.0
        virtual_pnl_acc = 0.0
        final_exit_price = 0.0
        trims_triggered = []
        
        entry_price = float(row['Price'])
        
        for _, msg in trader_msgs.iterrows():
            # Check for empty content (attachment fallback)
            has_attachments = pd.isna(msg['Content']) or not msg['Content']
            is_exit, qty_pct, msg_price, is_stop = detect_exit_signal(msg['Content'], has_attachments)
            
            if is_exit:
                exit_qty = min(position_remaining, qty_pct)
                if exit_qty <= 0:
                    break
                    
                # Use parsed price if available, otherwise delta-approximate or use actual exit price as fallback
                if msg_price is not None:
                    exit_price = msg_price
                else:
                    exit_price = float(row['STC-Price']) if pd.notnull(row['STC-Price']) else entry_price
                    
                pnl_pct = (exit_price - entry_price) / entry_price * 100
                virtual_pnl_acc += pnl_pct * exit_qty
                position_remaining -= exit_qty
                final_exit_price = exit_price
                trims_triggered.append(f"Trim {int(exit_qty*100)}% @ {exit_price}")
                
                if position_remaining <= 0:
                    break
                    
        # Close remaining at standard STC price if any left
        if position_remaining > 0:
            exit_price = float(row['STC-Price']) if pd.notnull(row['STC-Price']) else entry_price
            pnl_pct = (exit_price - entry_price) / entry_price * 100
            virtual_pnl_acc += pnl_pct * position_remaining
            final_exit_price = exit_price
            
        # Update columns
        trim_df.loc[idx, 'PnL'] = virtual_pnl_acc
        trim_df.loc[idx, 'PnL-actual'] = virtual_pnl_acc
        mutipl = 1 if row['Asset'] == 'option' else 0.01
        pnl_dollar = virtual_pnl_acc * entry_price * mutipl * float(row['Qty'])
        trim_df.loc[idx, 'PnL$'] = pnl_dollar
        trim_df.loc[idx, 'PnL$-actual'] = pnl_dollar
        trim_df.loc[idx, 'STC-Price'] = final_exit_price
        trim_df.loc[idx, 'STC-Price-actual'] = final_exit_price
        trim_df.loc[idx, 'TrailStats'] = " | ".join(trims_triggered) if trims_triggered else "None"
        
    return trim_df

def run_mae_strategy(portfolio_csv, multiplier=1.5, default_mae=20.0):
    """
    Strategy 2: MAE-Based Fixed Stop (Per-Trader).
    Sets stop-loss at 1.5x of the trader's historical average adverse excursion,
    with a 2:1 Reward-to-Risk profit target.
    """
    df = pd.read_csv(portfolio_csv)
    mae_df = df.copy()
    
    # 1. Parse and populate MAE per trade
    trade_maes = []
    for idx, row in mae_df.iterrows():
        mae, mfe, mae_sec, mfe_sec, _ = parse_trail_stats(row.get('TrailStats'))
        if mae is None:
            mae = default_mae
        trade_maes.append((idx, row['Trader'], mae, mfe, mae_sec, mfe_sec))
        
    mae_temp_df = pd.DataFrame(trade_maes, columns=['idx', 'Trader', 'MAE', 'MFE', 'MAE_Sec', 'MFE_Sec'])
    
    # Calculate average MAE per trader
    trader_avg_maes = mae_temp_df.groupby('Trader')['MAE'].mean().to_dict()
    
    for idx, row in mae_df.iterrows():
        trader = row['Trader']
        avg_mae = trader_avg_maes.get(trader, default_mae)
        
        # Stop loss and Profit target levels
        sl_pct = avg_mae * multiplier
        pt_pct = sl_pct * 2.0  # 2:1 RR
        
        entry_price = float(row['Price'])
        original_stc_pnl = float(row['PnL']) if pd.notnull(row['PnL']) else 0.0
        
        # Get trade excursions from temp df
        t_row = mae_temp_df.loc[mae_temp_df['idx'] == idx].iloc[0]
        actual_mae = t_row['MAE']
        actual_mfe = t_row['MFE']
        mae_sec = t_row['MAE_Sec']
        mfe_sec = t_row['MFE_Sec']
        
        triggered_sl = actual_mae >= sl_pct
        triggered_pt = actual_mfe is not None and actual_mfe >= pt_pct
        
        sim_pnl = original_stc_pnl
        exit_price = float(row['STC-Price']) if pd.notnull(row['STC-Price']) else entry_price
        
        if triggered_sl and triggered_pt:
            # Both triggered! Determine which one happened first using duration offset
            if mae_sec is not None and mfe_sec is not None:
                if mae_sec < mfe_sec:
                    sim_pnl = -sl_pct
                    exit_price = entry_price * (1.0 - sl_pct / 100)
                else:
                    sim_pnl = pt_pct
                    exit_price = entry_price * (1.0 + pt_pct / 100)
            else:
                # Conservative fallback: assume stop-loss triggered first
                sim_pnl = -sl_pct
                exit_price = entry_price * (1.0 - sl_pct / 100)
        elif triggered_sl:
            sim_pnl = -sl_pct
            exit_price = entry_price * (1.0 - sl_pct / 100)
        elif triggered_pt:
            sim_pnl = pt_pct
            exit_price = entry_price * (1.0 + pt_pct / 100)
            
        # Update columns
        mae_df.loc[idx, 'PnL'] = sim_pnl
        mae_df.loc[idx, 'PnL-actual'] = sim_pnl
        mutipl = 1 if row['Asset'] == 'option' else 0.01
        pnl_dollar = sim_pnl * entry_price * mutipl * float(row['Qty'])
        mae_df.loc[idx, 'PnL$'] = pnl_dollar
        mae_df.loc[idx, 'PnL$-actual'] = pnl_dollar
        mae_df.loc[idx, 'STC-Price'] = exit_price
        mae_df.loc[idx, 'STC-Price-actual'] = exit_price
        mae_df.loc[idx, 'SL'] = sl_pct
        
    return mae_df

def run_fixed_ts_strategy(portfolio_csv, ts_pct=30.0):
    """
    Strategy 3: Fixed % Trailing Stop.
    Applies a trailing stop percentage to each trade.
    """
    df = pd.read_csv(portfolio_csv)
    ts_df = df.copy()
    
    for idx, row in ts_df.iterrows():
        entry_price = float(row['Price'])
        original_stc_pnl = float(row['PnL']) if pd.notnull(row['PnL']) else 0.0
        
        # Check if pre-calculated in TrailStats
        mae, mfe, mae_sec, mfe_sec, ts_sims = parse_trail_stats(row.get('TrailStats'))
        
        sim_pnl = original_stc_pnl
        exit_price = float(row['STC-Price']) if pd.notnull(row['STC-Price']) else entry_price
        
        # Match closest pre-computed TS in TrailStats
        matched = False
        if ts_sims:
            # ts_pct is e.g. 30%. Look for closest simulated TS% in [20, 30, 40, 50]
            closest_ts = min(ts_sims.keys(), key=lambda k: abs(k - ts_pct))
            if abs(closest_ts - ts_pct) <= 5.0:
                sim_pnl = ts_sims[closest_ts]
                exit_price = entry_price * (1.0 + sim_pnl / 100)
                matched = True
                
        # If not matched or TrailStats missing, synthesize path using yfinance
        if not matched:
            quotes = get_synthetic_option_quotes(row['Symbol'], row['Date'], row.get('STC-Date', row['Date']), entry_price)
            if quotes is not None and not quotes.empty:
                # Trailing stop simulation loop
                peak = entry_price
                stopped = False
                ts_ratio = ts_pct / 100.0
                
                for _, q_row in quotes.iterrows():
                    curr_price = q_row['high']
                    if curr_price > peak:
                        peak = curr_price
                    
                    # Stop-loss calculation
                    stop_level = peak * (1.0 - ts_ratio)
                    if q_row['low'] <= stop_level:
                        exit_price = stop_level
                        sim_pnl = (exit_price - entry_price) / entry_price * 100
                        stopped = True
                        break
                        
                if not stopped:
                    # exit at final close price
                    exit_price = quotes['last'].iloc[-1]
                    sim_pnl = (exit_price - entry_price) / entry_price * 100
                    
        # Update columns
        ts_df.loc[idx, 'PnL'] = sim_pnl
        ts_df.loc[idx, 'PnL-actual'] = sim_pnl
        mutipl = 1 if row['Asset'] == 'option' else 0.01
        pnl_dollar = sim_pnl * entry_price * mutipl * float(row['Qty'])
        ts_df.loc[idx, 'PnL$'] = pnl_dollar
        ts_df.loc[idx, 'PnL$-actual'] = pnl_dollar
        ts_df.loc[idx, 'STC-Price'] = exit_price
        ts_df.loc[idx, 'STC-Price-actual'] = exit_price
        
    return ts_df

_global_atr_cache = {}

def run_atr_ts_strategy(portfolio_csv, n_atr=2.0, default_delta=0.40):
    """
    Strategy 4: Dynamic ATR Trailing Stop.
    Computes trailing stop distance as N * ATR of the underlying asset,
    translated to option prices using Delta approximation.
    """
    df = pd.read_csv(portfolio_csv)
    atr_df = df.copy()
    
    for idx, row in atr_df.iterrows():
        entry_price = float(row['Price'])
        original_stc_pnl = float(row['PnL']) if pd.notnull(row['PnL']) else 0.0
        
        symbol = row['Symbol']
        is_option = "_" in symbol
        underlying = symbol.split("_")[0] if is_option else symbol
        if underlying.startswith('/') or underlying.startswith('@'):
            underlying = underlying[1:] + "=F"
            
        # Get daily ATR
        atr = _global_atr_cache.get(underlying)
        if atr is None:
            # Check if we already know this symbol is delisted/failed
            if underlying in _underlying_daily_cache and _underlying_daily_cache[underlying].empty:
                atr = entry_price * 0.05
                _global_atr_cache[underlying] = atr

        if atr is None:
            # Ensure broad history is cached first to avoid network requests
            get_underlying_daily_history(underlying, row['Date'], row.get('STC-Date', row['Date']))
            cached_hist = _underlying_daily_cache.get(underlying)
            if cached_hist is not None and not cached_hist.empty and len(cached_hist) >= 14:
                try:
                    high_low = cached_hist['High'] - cached_hist['Low']
                    high_close = np.abs(cached_hist['High'] - cached_hist['Close'].shift())
                    low_close = np.abs(cached_hist['Low'] - cached_hist['Close'].shift())
                    ranges = pd.concat([high_low, high_close, low_close], axis=1)
                    true_range = np.max(ranges, axis=1)
                    atr = true_range.rolling(14).mean().iloc[-1]
                    _global_atr_cache[underlying] = atr
                except Exception:
                    pass
                    
        if atr is None:
            try:
                hist = yf.Ticker(underlying).history(period="1mo", interval="1d")
                if not hist.empty and len(hist) >= 14:
                    high_low = hist['High'] - hist['Low']
                    high_close = np.abs(hist['High'] - hist['Close'].shift())
                    low_close = np.abs(hist['Low'] - hist['Close'].shift())
                    ranges = pd.concat([high_low, high_close, low_close], axis=1)
                    true_range = np.max(ranges, axis=1)
                    atr = true_range.rolling(14).mean().iloc[-1]
                    _global_atr_cache[underlying] = atr
            except Exception:
                pass
                
        if atr is None:
            atr = entry_price * 0.05  # fallback to 5% volatility
            # Cache the fallback ATR so we don't query yfinance again
            _global_atr_cache[underlying] = atr
            
        # Convert ATR to option stop distance pct
        if is_option:
            atr_option = atr * default_delta
            stop_distance_pct = (atr_option / entry_price) * 100.0 * n_atr
        else:
            stop_distance_pct = (atr / entry_price) * 100.0 * n_atr
            
        # Bound stop distance between 10% and 60%
        stop_distance_pct = max(10.0, min(60.0, stop_distance_pct))
        
        # Now run Strategy 3 simulator with this dynamic stop percentage
        sim_pnl = original_stc_pnl
        exit_price = float(row['STC-Price']) if pd.notnull(row['STC-Price']) else entry_price
        
        quotes = get_synthetic_option_quotes(row['Symbol'], row['Date'], row.get('STC-Date', row['Date']), entry_price)
        if quotes is not None and not quotes.empty:
            peak = entry_price
            stopped = False
            ts_ratio = stop_distance_pct / 100.0
            
            for _, q_row in quotes.iterrows():
                curr_price = q_row['high']
                if curr_price > peak:
                    peak = curr_price
                
                stop_level = peak * (1.0 - ts_ratio)
                if q_row['low'] <= stop_level:
                    exit_price = stop_level
                    sim_pnl = (exit_price - entry_price) / entry_price * 100
                    stopped = True
                    break
                    
            if not stopped:
                exit_price = quotes['last'].iloc[-1]
                sim_pnl = (exit_price - entry_price) / entry_price * 100
                
        # Update columns
        atr_df.loc[idx, 'PnL'] = sim_pnl
        atr_df.loc[idx, 'PnL-actual'] = sim_pnl
        mutipl = 1 if row['Asset'] == 'option' else 0.01
        pnl_dollar = sim_pnl * entry_price * mutipl * float(row['Qty'])
        atr_df.loc[idx, 'PnL$'] = pnl_dollar
        atr_df.loc[idx, 'PnL$-actual'] = pnl_dollar
        atr_df.loc[idx, 'STC-Price'] = exit_price
        atr_df.loc[idx, 'STC-Price-actual'] = exit_price
        atr_df.loc[idx, 'SL'] = stop_distance_pct
        
    return atr_df

# ==========================================
# PART 4: Sweep Optimization & Integration
# ==========================================

def run_backtests_and_optimizations():
    """
    Main runner script to run backtest scans, optimize exit parameters,
    and save Strategy 1, 2, 3, and 4 portfolio CSV files.
    """
    data_dir = os.path.join(cfg['root']['dir'], '..', 'data')
    portfolio_source = os.path.join(data_dir, 'analysts_portfolio_bulltrades_5-10_8-8.csv')
    
    if not os.path.exists(portfolio_source):
        print(f"Error: Source portfolio not found at {portfolio_source}")
        return
        
    print(f"Loading historical training set from: {portfolio_source}")
    
    # 1. STRATEGY 1: Trim/Screenshot exit parsing
    print("\n--- Strategy 1: Running Trim / Screenshot Detector backtest ---")
    # Load all historical message files to scan
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
        
    strat1_portfolio = run_trim_strategy(portfolio_source, all_msgs)
    strat1_path = os.path.join(data_dir, 'strat_trim_portfolio.csv')
    strat1_portfolio.to_csv(strat1_path, index=False)
    print(f"Strategy 1 results saved to: {strat1_path}")
    
    # 2. STRATEGY 2: MAE Stop Loss Optimization
    print("\n--- Strategy 2: Sweeping MAE Stop Multipliers ---")
    best_mae_mult = 1.5
    best_mae_pnl = -float('inf')
    best_mae_df = None
    
    for mult in [1.0, 1.25, 1.5, 2.0, 2.5]:
        mae_df = run_mae_strategy(portfolio_source, multiplier=mult)
        total_pnl = mae_df['PnL$'].sum()
        print(f"Multiplier: {mult}x MAE | Total Profit: ${total_pnl:,.2f}")
        if total_pnl > best_mae_pnl:
            best_mae_pnl = total_pnl
            best_mae_mult = mult
            best_mae_df = mae_df
            
    print(f"Optimal MAE Multiplier identified: {best_mae_mult}x MAE (Profit: ${best_mae_pnl:,.2f})")
    strat2_path = os.path.join(data_dir, 'strat_mae_stop_portfolio.csv')
    best_mae_df.to_csv(strat2_path, index=False)
    print(f"Strategy 2 results saved to: {strat2_path}")
    
    # 3. STRATEGY 3: Fixed Trailing Stop Sweep Optimization
    print("\n--- Strategy 3: Sweeping Fixed % Trailing Stops ---")
    best_ts_pct = 30.0
    best_ts_pnl = -float('inf')
    best_ts_df = None
    
    for pct in [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0, 60.0, 70.0]:
        ts_df = run_fixed_ts_strategy(portfolio_source, ts_pct=pct)
        total_pnl = ts_df['PnL$'].sum()
        print(f"TS Percentage: {pct}% | Total Profit: ${total_pnl:,.2f}")
        if total_pnl > best_ts_pnl:
            best_ts_pnl = total_pnl
            best_ts_pct = pct
            best_ts_df = ts_df
            
    print(f"Optimal Trailing Stop identified: {best_ts_pct}% (Profit: ${best_ts_pnl:,.2f})")
    strat3_path = os.path.join(data_dir, 'strat_fixed_ts_portfolio.csv')
    best_ts_df.to_csv(strat3_path, index=False)
    print(f"Strategy 3 results saved to: {strat3_path}")
    
    # 4. STRATEGY 4: Dynamic ATR Trailing Stop
    print("\n--- Strategy 4: Sweeping Dynamic ATR Multipliers ---")
    best_atr_n = 2.0
    best_atr_pnl = -float('inf')
    best_atr_df = None
    
    for n in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        atr_df = run_atr_ts_strategy(portfolio_source, n_atr=n)
        total_pnl = atr_df['PnL$'].sum()
        print(f"ATR Multiplier N: {n} | Total Profit: ${total_pnl:,.2f}")
        if total_pnl > best_atr_pnl:
            best_atr_pnl = total_pnl
            best_atr_n = n
            best_atr_df = atr_df
            
    print(f"Optimal ATR Multiplier identified: {best_atr_n} (Profit: ${best_atr_pnl:,.2f})")
    strat4_path = os.path.join(data_dir, 'strat_atr_ts_portfolio.csv')
    best_atr_df.to_csv(strat4_path, index=False)
    print(f"Strategy 4 results saved to: {strat4_path}")
    
    # 5. Generate Side-by-Side Comparison
    print("\n--- Generating Strategy Comparison Report ---")
    generate_strategy_comparison(portfolio_source, strat1_path, strat2_path, strat3_path, strat4_path)

def generate_strategy_comparison(original_path, strat1_path, strat2_path, strat3_path, strat4_path):
    """
    Computes summary metrics for each portfolio side-by-side and saves to strategy_comparison.csv
    """
    paths = {
        "Original STC": original_path,
        "Strategy 1 (Trim Detector)": strat1_path,
        "Strategy 2 (Optimized MAE)": strat2_path,
        "Strategy 3 (Optimized Fixed TS)": strat3_path,
        "Strategy 4 (Optimized ATR TS)": strat4_path
    }
    
    comparison_metrics = []
    
    for name, path in paths.items():
        if not os.path.exists(path):
            continue
            
        df = pd.read_csv(path)
        closed_trades = df[df['isOpen'] == 0]
        
        total_trades = len(closed_trades)
        if total_trades == 0:
            continue
            
        pnl_col = 'PnL$' if 'PnL$' in closed_trades.columns else 'PnL$-actual'
        returns_col = 'PnL' if 'PnL' in closed_trades.columns else 'PnL-actual'
        
        wins = closed_trades[closed_trades[pnl_col].astype(float) > 0]
        losses = closed_trades[closed_trades[pnl_col].astype(float) <= 0]
        
        win_rate = len(wins) / total_trades * 100
        total_profit = closed_trades[pnl_col].sum()
        avg_return = closed_trades[returns_col].mean()
        
        gross_profit = wins[pnl_col].sum()
        gross_loss = abs(losses[pnl_col].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate max drawdown on cumulative profit curve
        cum_pnl = closed_trades[pnl_col].cumsum()
        running_max = cum_pnl.cummax()
        drawdowns = running_max - cum_pnl
        max_drawdown = drawdowns.max()
        
        comparison_metrics.append({
            "Strategy": name,
            "Total Trades": total_trades,
            "Win Rate %": round(win_rate, 2),
            "Total Profit $": round(total_profit, 2),
            "Avg Return %": round(avg_return, 2),
            "Profit Factor": round(profit_factor, 2) if not np.isinf(profit_factor) else "N/A",
            "Max Drawdown $": round(max_drawdown, 2)
        })
        
    comp_df = pd.DataFrame(comparison_metrics)
    output_path = os.path.join(os.path.dirname(original_path), 'strategy_comparison.csv')
    comp_df.to_csv(output_path, index=False)
    print(f"\nHead-to-head comparison saved successfully to: {output_path}")
    
    # Print nice table to stdout
    print("\n" + "="*80)
    print(f"{'EXIT STRATEGY COMPARISON TABLE':^80}")
    print("="*80)
    print(f"{'Strategy':<30} | {'Trades':<6} | {'Win %':<7} | {'Net Profit':<11} | {'Avg Ret %':<9} | {'PF':<5}")
    print("-"*80)
    for _, row in comp_df.iterrows():
        print(f"{row['Strategy']:<30} | {row['Total Trades']:<6} | {row['Win Rate %']:<7.2f} | ${row['Total Profit $']:<10,.2f} | {row['Avg Return %']:<9.2f} | {row['Profit Factor']}")
    print("="*80)

if __name__ == "__main__":
    run_backtests_and_optimizations()
