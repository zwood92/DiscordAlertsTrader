import sys
import os

sys.path.append(os.path.dirname(__file__))

from DiscordAlertsTrader.message_parser import parse_trade_alert

msgs = [
    "MNQ shorts@ 410", # Jose
    "5/08 META 625c @.60| 10 CONTRACTS", # Everest
    "Ticker:\nMNq short\nEntry:\n29305", # Guru
    "$TSLA 5/8 432.50 CALL @ 1.00", # Ultra
    "SHORTING @425" # Vix
]

for msg in msgs:
    print(f"\n--- Parsing message: {msg[:30]}... ---")
    pars, order = parse_trade_alert(msg)
    if order:
        print("Order Output:", order)
    else:
        print("FAILED TO PARSE")
