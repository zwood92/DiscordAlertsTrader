
import PySimpleGUIQt as sg
from DiscordAlertsTrader import gui_layouts as gl
from DiscordAlertsTrader.configurator import cfg

# Mock data
fnt_b = ("Helvetica", 11)
fnt_h = ("Helvetica", 12, "bold")

try:
    ly = gl.layout_dashboard([], [], [])
    print("Dashboard layout OK")
    ly = gl.layout_side_panel()
    print("Side panel layout OK")
    ly = gl.layout_config(fnt_h, cfg)
    print("Config layout OK")
except Exception as e:
    print(f"Error: {e}")
