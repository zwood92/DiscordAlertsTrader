import re

msgs = [
    "MNQ shorts@ 410",
    "ES longs@ 5000",
    "🚀5/08 $META 625c @.60| 10 CONTRACTS🚀",
    "Ticker:\nMNq short\nEntry:\n29305"
]

for msg in msgs:
    print(f"\n--- Testing message: {msg[:30]}... ---")
    
    # 1. Everest Options Format
    everest_pattern = r'(?i)(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\s*\$?([A-Z]+)\s*(\d+[.\d]*[cp]?)\s*@\s*\.?(\d+(?:[,.]\d+)?)'
    ev_match = re.search(everest_pattern, msg)
    if ev_match:
        expDate, ticker, strike, price = ev_match.groups()
        action = "BTO"
        
        # Check for contracts
        quantity = None
        qty_pattern = r'\|\s*(\d+)\s*CONTRACTS'
        qty_match = re.search(qty_pattern, msg, re.IGNORECASE)
        if qty_match:
            quantity = qty_match.groups()[0]
        
        print(f"[EVEREST MATCH] Action: {action}, Ticker: {ticker}, Strike: {strike}, Exp: {expDate}, Price: {price}, Qty: {quantity}")
        continue
    
    # 2. Market Guru Format
    guru_pattern = r'(?i)Ticker:\s*\n?\s*((?:\/|@)?[A-Z0-9]+)\s+(short|long)\s*\n?\s*Entry:\s*\n?\s*(\d+(?:[,.]\d+)?)'
    gu_match = re.search(guru_pattern, msg)
    if gu_match:
        ticker, direction, price = gu_match.groups()
        action = "STO" if "short" in direction.lower() else "BTO"
        if not ticker.startswith('/') and not ticker.startswith('@'):
            ticker = '/' + ticker.upper()
        print(f"[GURU MATCH] Action: {action}, Ticker: {ticker.upper()}, Price: {price}")
        continue

    # 3. Jose Futures Format
    jose_pattern = r'(?i)(?:^|\n)\s*((?:\/|@)?[A-Z0-9]+)\s+(shorts?|longs?)\s*@\s*(\d+(?:[,.]\d+)?)'
    jo_match = re.search(jose_pattern, msg)
    if jo_match:
        ticker, direction, price = jo_match.groups()
        action = "STO" if "short" in direction.lower() else "BTO"
        if not ticker.startswith('/') and not ticker.startswith('@'):
            ticker = '/' + ticker.upper()
        print(f"[JOSE MATCH] Action: {action}, Ticker: {ticker.upper()}, Price: {price}")
        continue
        
    print("[NO MATCH]")

