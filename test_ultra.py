import re

msg = "$TSLA 5/8 432.50 CALL @ 1.00"

print(f"\n--- Testing message: {msg} ---")

ultra_pattern = r'(?i)\$?([A-Z]+)\s+(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\s+(\d+(?:\.\d+)?)\s+(CALL|PUT|C|P)S?\s*@\s*\.?(\d+(?:[,.]\d+)?)'
match = re.search(ultra_pattern, msg)

if match:
    ticker, expDate, strike_num, opt_type, price = match.groups()
    action = "BTO"
    strike = strike_num + opt_type[0].lower()
    print(f"[ULTRA MATCH] Action: {action}, Ticker: {ticker}, Strike: {strike}, Exp: {expDate}, Price: {price}")
else:
    print("[NO MATCH]")
