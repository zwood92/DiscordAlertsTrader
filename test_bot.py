import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from DiscordAlertsTrader.discord_bot import DiscordBot
    print("SUCCESS: DiscordBot class imported successfully without syntax errors!")
except Exception as e:
    import traceback
    print("ERROR importing DiscordBot:")
    traceback.print_exc()
    sys.exit(1)
