# DiscordAlertsTrader

## Project Overview
DiscordAlertsTrader is a Python package that automates stock/options trades based on alerts shared by analysts in Discord channels. It parses trading signals (e.g., BTO, STC, SL, PT) and executes trades via broker APIs (TradeStation, eTrade, Webull, IBKR). It features a GUI for tracking signals, monitoring real-time performance, and manually/automatically triggering alerts.

## Building and Running
- **Install dependencies:** `pip install -e .` (Requires Python 3.10)
- **Configuration:** Copy `DiscordAlertsTrader/config_example.ini` to `DiscordAlertsTrader/config.ini` and set up the Discord user token, channel IDs, and broker API keys.
- **Run the Application:** Run `DiscordAlertsTrader` in the terminal to launch the GUI and start listening for Discord alerts.

## Development Conventions & AI Assistant Protocols
All AI assistants MUST adhere to the following token-optimization protocols to aggressively manage API usage costs:

1. **Caveman Protocol**: Communicate in brief, telegraphic outputs. Why use many tokens when few tokens do trick?
2. **Codeburn Protocol**: Strip unnecessary comments, prints, and dead code during refactors to minimize code token footprints.
3. **Design Extract**: When analyzing external web designs or UI components, use design extraction techniques (e.g. `npx designlang <url>`) rather than ingesting raw HTML/CSS.