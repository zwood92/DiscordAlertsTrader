import sys
import os
import traceback

sys.path.append(os.path.dirname(__file__))

print("--- Testing ATR Logic ---")
from DiscordAlertsTrader.alerts_trader import AlertsTrader
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.analytics import get_atr

# Mocking Brokerage Session
class MockSession:
    name = "mock"
    def get_account_info(self):
        return {'securitiesAccount': {'currentBalances': {'liquidationValue': 100000}}}

class MockTrader(AlertsTrader):
    def __init__(self):
        self.bksession = MockSession()
        self.cfg = cfg
        self.queue_prints = type('obj', (object,), {'put': lambda self, x: None})()
    
    def test_calculate_stoploss(self):
        order = {}
        trade = {'Symbol': 'SPY', 'Price': 500}
        
        # Test percentage
        res1 = self.calculate_stoploss(order.copy(), trade, "10%")
        print(f"10% SL -> trail_stop_const: {res1.get('trail_stop_const')}")
        
        # Test ATR
        res2 = self.calculate_stoploss(order.copy(), trade, "ATR_2x")
        print(f"ATR_2x SL -> trail_stop_const: {res2.get('trail_stop_const')}")
        
        # Test Fallback (Bad Ticker)
        trade2 = {'Symbol': 'BADTICKER999', 'Price': 100}
        res3 = self.calculate_stoploss(order.copy(), trade2, "ATR_1.5")
        print(f"ATR_1.5 SL (Bad Ticker) -> trail_stop_const: {res3.get('trail_stop_const')}")

trader = MockTrader()
trader.test_calculate_stoploss()

print("\n--- Testing MAE/MFE Logic ---")
import pandas as pd
from DiscordAlertsTrader.analytics import calculate_excursions

# Create a mock portfolio CSV with recent trades
mock_csv = "mock_portfolio.csv"
data = {
    'Date': [pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S.%f")],
    'Symbol': ['AAPL'],
    'Type': ['BTO'],
    'Price': [150.0],
    'Price-alert': [150.0],
    'Trader': ['mock_analyst'],
    'isOpen': [1]
}
df = pd.DataFrame(data)
df.to_csv(mock_csv, index=False)

calculate_excursions(mock_csv)

df_res = pd.read_csv(mock_csv)
print("Resulting DataFrame columns:")
print(df_res.columns)
print("MAE:", df_res.iloc[0]['MAE'])
print("MFE:", df_res.iloc[0]['MFE'])

# Cleanup
if os.path.exists(mock_csv):
    os.remove(mock_csv)
