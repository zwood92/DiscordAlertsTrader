import sys
import os
import traceback

sys.path.append(os.path.dirname(__file__))

print("--- Checking Syntax ---")
try:
    import DiscordAlertsTrader.gui
    import DiscordAlertsTrader.gui_layouts
    import DiscordAlertsTrader.alerts_trader
    import DiscordAlertsTrader.message_parser
    print("Syntax check passed.")
except Exception as e:
    print("Syntax Error:")
    traceback.print_exc()
    sys.exit(1)

print("\n--- Testing Parser (Futures) ---")
from DiscordAlertsTrader.message_parser import parse_trade_alert

alerts = [
    "BTO 2 /ES @ 5000",
    "STC 1 /NQ @ 18000",
    "BTO @ES 5000"
]

for alert in alerts:
    _, order = parse_trade_alert(alert)
    print(f"Alert: {alert}")
    if order:
        print(f"  Asset: {order.get('asset')}, Symbol: {order.get('Symbol')}, Qty: {order.get('Qty')}")
    else:
        print("  Failed to parse")

print("\n--- Testing Sizing Logic ---")
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.alerts_trader import AlertsTrader

# Mocking
class MockSession:
    name = "mock"
    def get_account_info(self):
        return {'securitiesAccount': {'currentBalances': {'liquidationValue': 100000}}}

class MockTrader(AlertsTrader):
    def __init__(self):
        self.bksession = MockSession()
        self.cfg = cfg
        self.max_trade_val = 5000
    
    def test_size(self, order, price):
        cfg['risk_management']['sizing_type'] = 'dollar'
        trade_capitals = {'default': 1000}
        trade_capital = float(trade_capitals.get(order.get("Trader"), trade_capitals["default"]))
        
        sizing_type = cfg['risk_management'].get('sizing_type', 'dollar')
        
        # Dollar
        cfg['risk_management']['sizing_type'] = 'dollar'
        order_dollar = order.copy()
        if order_dollar['asset'] == 'option':
            order_dollar['Qty'] = int(round(trade_capital / (price * 100)))
        else:
            order_dollar['Qty'] = int(trade_capital // price)
        print(f"Dollar size (cap {trade_capital}, price {price}): {order_dollar['Qty']}")

        # Percent
        cfg['risk_management']['sizing_type'] = 'percent'
        cfg['risk_management']['percent_per_trade'] = '2'
        order_pct = order.copy()
        balance = 100000
        pct = 2 / 100
        trade_cap_pct = balance * pct
        if order_pct['asset'] == 'option':
            order_pct['Qty'] = int(round(trade_cap_pct / (price * 100)))
        else:
            order_pct['Qty'] = int(trade_cap_pct // price)
        print(f"Percent size (balance {balance}, 2%, price {price}): {order_pct['Qty']}")

        # Contracts
        cfg['risk_management']['sizing_type'] = 'contracts'
        cfg['risk_management']['fixed_qty'] = '5'
        order_fix = order.copy()
        order_fix['Qty'] = int(cfg['risk_management'].get('fixed_qty', 1))
        print(f"Fixed size (5): {order_fix['Qty']}")

trader = MockTrader()
print("Option trade:")
trader.test_size({'asset': 'option', 'Trader': 'default'}, 2.50)
print("Stock/Future trade:")
trader.test_size({'asset': 'future', 'Trader': 'default'}, 100)

