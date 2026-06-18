import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from DiscordAlertsTrader import gui_generator as gg

try:
    exclude = {"stocks": True, "options": False}
    p_data = gg.get_portf_data(exclude)
    t_data = gg.get_tracker_data(exclude)
    s_data = gg.get_stats_data(exclude)
    print("p_data loaded, rows:", len(p_data[0]) if p_data and p_data[0] else 0)
    print("t_data loaded, rows:", len(t_data[0]) if t_data and t_data[0] else 0)
    print("s_data loaded, rows:", len(s_data[0]) if s_data and s_data[0] else 0)
    
    metrics = gg.get_dashboard_metrics(p_data, t_data, s_data, timeframe="This Month")
    print("Metrics succeeded:", metrics)
except Exception as e:
    import traceback
    traceback.print_exc()
