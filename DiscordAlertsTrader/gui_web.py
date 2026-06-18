import os
import sys
import json
import time
import asyncio
import queue
import threading
import webbrowser
from datetime import datetime
from aiohttp import web
import pandas as pd

from DiscordAlertsTrader.brokerages import get_brokerage
from DiscordAlertsTrader import gui_generator as gg
from DiscordAlertsTrader.discord_bot import DiscordBot
from DiscordAlertsTrader.configurator import cfg, channel_ids, get_discord_token, config_path, update_port_cols
from DiscordAlertsTrader.message_parser import parse_trade_alert, ordersymb_to_str

# Global references
bksession = None
alistner = None
trade_events = queue.Queue(maxsize=100)
active_websockets = set()
loop = None

# A queue parser that runs in the server event loop and broadcasts to WebSockets
async def poll_trade_events():
    while True:
        try:
            # Non-blocking check of queue
            if not trade_events.empty():
                item = trade_events.get_nowait()
                # format: [text, text_color, background_color] or [text, text_color]
                msg_data = {
                    "text": item[0],
                    "color": item[1] if len(item) > 1 else "",
                    "bg": item[2] if len(item) > 2 else ""
                }
                # broadcast
                disconnected = set()
                for ws in active_websockets:
                    try:
                        await ws.send_json({"type": "log", "data": msg_data})
                    except Exception:
                        disconnected.add(ws)
                active_websockets.difference_update(disconnected)
        except Exception as e:
            pass
        await asyncio.sleep(0.1)

# REST API Handlers
async def handle_portfolio(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    exclude = {
        "Closed": body.get("Closed", False),
        "Open": body.get("Open", False),
        "Canceled": body.get("Canceled", True),
        "Rejected": body.get("Rejected", True),
        "NegPnL": body.get("NegPnL", False),
        "PosPnL": body.get("PosPnL", False),
        "live PnL": body.get("live PnL", False),
        "stocks": body.get("stocks", True),
        "options": body.get("options", False),
        "bto": body.get("bto", False),
        "sto": body.get("sto", False)
    }
    
    kwargs = {
        "port_filt_author": body.get("filt_author", "All"),
        "port_filt_date_frm": body.get("filt_date_frm", "week"),
        "port_filt_date_to": body.get("filt_date_to", "today"),
        "port_filt_sym": body.get("filt_sym", ""),
        "port_filt_chn": body.get("filt_chn", ""),
        "port_exc_author": body.get("exc_author", ""),
        "port_exc_chn": body.get("exc_chn", "")
    }
    
    data, headers = gg.get_portf_data(exclude, **kwargs)
    return web.json_response({"headers": headers, "data": data})

async def handle_tracker(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    exclude = {
        "Closed": body.get("Closed", False),
        "Open": body.get("Open", False),
        "NegPnL": body.get("NegPnL", False),
        "PosPnL": body.get("PosPnL", False),
        "live PnL": body.get("live PnL", False),
        "stocks": body.get("stocks", True),
        "options": body.get("options", False),
        "bto": body.get("bto", False),
        "sto": body.get("sto", False)
    }
    
    kwargs = {
        "track_filt_author": body.get("filt_author", "All"),
        "track_filt_date_frm": body.get("filt_date_frm", "week"),
        "track_filt_date_to": body.get("filt_date_to", ""),
        "track_filt_sym": body.get("filt_sym", ""),
        "track_filt_chn": body.get("filt_chn", ""),
        "track_exc_author": body.get("exc_author", ""),
        "track_exc_sym": body.get("exc_sym", ""),
        "track_exc_chn": body.get("exc_chn", ""),
        "track_dte_min": body.get("dte_min", ""),
        "track_dte_max": body.get("dte_max", "")
    }
    
    data, headers = gg.get_tracker_data(exclude, **kwargs)
    return web.json_response({"headers": headers, "data": data})

async def handle_stats(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    exclude = {
        "NegPnL": body.get("NegPnL", False),
        "PosPnL": body.get("PosPnL", False),
        "stocks": body.get("stocks", True),
        "options": body.get("options", False),
        "bto": body.get("bto", False),
        "sto": body.get("sto", False)
    }
    
    kwargs = {
        "stat_filt_author": body.get("filt_author", "All"),
        "stat_filt_date_frm": body.get("filt_date_frm", "week"),
        "stat_filt_date_to": body.get("filt_date_to", ""),
        "stat_filt_sym": body.get("filt_sym", ""),
        "stat_max_trade_val": body.get("max_trade_val", ""),
        "stat_max_qty": body.get("max_qty", ""),
        "stat_exc_author": body.get("exc_author", ""),
        "stat_exc_sym": body.get("exc_sym", ""),
        "stat_exc_chn": body.get("exc_chn", ""),
        "stat_dte_min": body.get("dte_min", ""),
        "stat_dte_max": body.get("dte_max", "")
    }
    
    data, headers = gg.get_stats_data(exclude, **kwargs)
    return web.json_response({"headers": headers, "data": data})

async def handle_strategy_exits(request):
    comp_data, opt_data = gg.get_strategy_performance_data()
    return web.json_response({
        "comparison": {
            "headers": comp_data[1] if len(comp_data) > 1 else [],
            "data": comp_data[0] if len(comp_data) > 0 else []
        },
        "optimizations": {
            "headers": opt_data[1] if len(opt_data) > 1 else [],
            "data": opt_data[0] if len(opt_data) > 0 else []
        }
    })

async def handle_msg_history(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    chn = body.get("channel", list(channel_ids.keys())[0] if channel_ids else "")
    kwargs = {
        "filt_author": body.get("filt_author", ""),
        "filt_date_frm": body.get("filt_date_frm", "today"),
        "filt_date_to": body.get("filt_date_to", ""),
        "filt_cont": body.get("filt_cont", "")
    }
    
    data, headers = gg.get_hist_msgs(chan_name=chn, **kwargs)
    return web.json_response({"headers": headers, "data": data, "channels": list(channel_ids.keys())})

async def handle_dashboard(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    timeframe = body.get("timeframe", "This Month")
    
    # Grab background data grids first
    exclude = {"stocks": True, "options": False}
    p_data = gg.get_portf_data(exclude)
    t_data = gg.get_tracker_data(exclude)
    s_data = gg.get_stats_data(exclude)
    
    metrics = gg.get_dashboard_metrics(p_data, t_data, s_data, timeframe=timeframe)
    
    # Determine bot activity status
    bot_status = "ACTIVE" if alistner and alistner.ws is not None else "STOPPED"
    metrics["bot_status"] = bot_status
    
    # Sentiment radar
    sentiment = "NEUTRAL"
    rationale = "No recent rationale available."
    if alistner and not alistner.tracker.portfolio.empty:
        last_alert = alistner.tracker.portfolio.iloc[-1]
        if last_alert['isOpen'] == 1:
            sentiment = "BULLISH" if last_alert['Type'] == "BTO" else "BEARISH"
            rationale = f"Analyst {last_alert['Trader']} opened {last_alert['Symbol']} @ {last_alert['Price']}"
            
    metrics["sentiment"] = sentiment
    metrics["rationale"] = rationale
    
    # Equity curve graphic URL
    metrics["equity_chart_url"] = "/api/dashboard/chart?t=" + str(datetime.now().timestamp()) if metrics.get("chart_path") else ""
    
    return web.json_response(metrics)

async def handle_dashboard_chart(request):
    exclude = {"stocks": True, "options": False}
    p_data = gg.get_portf_data(exclude)
    t_data = gg.get_tracker_data(exclude)
    s_data = gg.get_stats_data(exclude)
    # This generates the image file to général data dir
    metrics = gg.get_dashboard_metrics(p_data, t_data, s_data, timeframe="This Month")
    path = metrics.get("chart_path", "")
    if path and os.path.exists(path):
        return web.FileResponse(path)
    return web.Response(status=404, text="Chart not found")

async def handle_account(request):
    if bksession is None:
        return web.json_response({"connected": False})
        
    try:
        acc_inf, ainf = gg.get_acc_bals(bksession)
        pos_tab, pos_headings = gg.get_pos(acc_inf)
        ord_tab, ord_headings, _ = gg.get_orders(acc_inf)
        
        return web.json_response({
            "connected": True,
            "broker": bksession.name,
            "info": ainf,
            "positions": {
                "headers": pos_headings,
                "data": pos_tab
            },
            "orders": {
                "headers": ord_headings,
                "data": ord_tab
            }
        })
    except Exception as e:
        return web.json_response({"connected": False, "error": str(e)})

async def handle_config_get(request):
    # Category configuration fields
    sections = {}
    for section in cfg.sections():
        if section == 'root':
            continue
        sections[section] = dict(cfg[section])
        
    # Inject default exits dictionary parsed fields
    try:
        exits_dict = eval(cfg['order_configs'].get('default_exits', '{"PT1": None, "PT2": None, "PT3": None, "SL": None}'))
    except Exception:
        exits_dict = {"PT1": None, "PT2": None, "PT3": None, "SL": None}
        
    sections['default_exits'] = {
        "PT1": exits_dict.get("PT1") or "",
        "PT2": exits_dict.get("PT2") or "",
        "PT3": exits_dict.get("PT3") or "",
        "SL": exits_dict.get("SL") or ""
    }
    
    return web.json_response({"config": sections, "subscribed_analysts": cfg['discord']['authors_subscribed'].split(',')})

async def handle_config_save(request):
    body = await request.json()
    
    # Save standard exits back into order_configs section
    exits_dict = {
        "PT1": body.get("cfg_exits_PT1", "").strip() or None,
        "PT2": body.get("cfg_exits_PT2", "").strip() or None,
        "PT3": body.get("cfg_exits_PT3", "").strip() or None,
        "SL": body.get("cfg_exits_SL", "").strip() or None
    }
    cfg['order_configs']['default_exits'] = str(exits_dict)
    
    # Update standard section fields
    for k, v in body.items():
        if k.startswith("cfg_"):
            if k.startswith("cfg_exits_"):
                continue
            # format: cfg_section.field = value
            parts = k.replace("cfg_", "").split(".")
            if len(parts) == 2:
                sec, field = parts
                cfg[sec][field] = str(v)
                
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            cfg.write(f)
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})

async def handle_quick_trade_trigger(request):
    body = await request.json()
    msg_str = body.get("message", "").strip()
    portfolio_choice = body.get("portfolio", "analysts")
    
    if not msg_str:
        return web.json_response({"success": False, "error": "Empty message string"})
        
    try:
        # Match author name
        author, alert = split_alert_message(msg_str)
        author = match_authors(author.strip())
        alert = alert.strip().replace("SPXW", "SPX")
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        chan = "GUI_" + portfolio_choice
        
        new_msg = pd.Series({
            'AuthorID': None,
            'Author': author,
            'Date': date_str, 
            'Content': alert,
            'Channel': chan
        })
        
        # Invoke new alert parser and tracker
        alistner.new_msg_acts(new_msg, from_disc=False)
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})

async def handle_quick_trade_action(request):
    body = await request.json()
    action = body.get("action", "") # BTO, BTC, STC, STO, scale, exits, exitupdate, quotes, plot
    msg_str = body.get("message", "").strip()
    qty_override = body.get("quantity", "")
    
    if not msg_str:
        return web.json_response({"success": False, "error": "Empty message string"})
        
    # Normalize price tags
    if "@" not in msg_str:
        msg_str += " @0.01"
    msg_str = msg_str.replace("@None", "@0.01").replace("@m", "@0.01")
    
    author, alert = split_alert_message(msg_str)
    
    # Overwrite manual qty if given
    import re
    pattern = r"(BTO|STO|STC|BTC)\s+(\d+)?\s+([A-Z0-9_]+)"
    match = re.search(pattern, alert)
    if match and qty_override:
        act, old_qty, symbol = match.groups()
        alert = alert.replace(f"{act} {old_qty if old_qty else ''}", f"{act} {qty_override}")
        
    if not any(a in alert for a in ["BTO", "STO", "BTC", "STC"]):
        alert = "BTO " + alert
        
    _, order = parse_trade_alert(alert)
    if order is None:
        return web.json_response({"success": False, "error": "Failed to parse trade alert"})
        
    symbol_str = ordersymb_to_str(order['Symbol'])
    if order.get('Qty') is None:
        order['Qty'] = 1
        
    # Get live quotes prices
    ask, bid = get_live_quotes_price(order['Symbol'])
    price = ask if order['action'] in ["BTO", "BTC"] else bid
    if price is None:
        price = order.get('price', 0.01)
        
    # Build updated message
    response_msg = ""
    if action == 'exitupdate':
        response_msg = f"{author}, Exit Update {symbol_str} PT 50% SL 50%"
    elif action == 'exits':
        response_msg = f"{author}, Exit Update {symbol_str} PT1 20% PT2 40% PT3 60% SL 50%"
    elif action == 'quotes':
        act_msg = order['action'].replace('ExitUpdate', "BTO")
        response_msg = f"{author}, {act_msg} {order['Qty']} {symbol_str} @{price} | [ask {ask} bid {bid}]"
    elif action in ["BTO", "BTC", "STO", "STC"]:
        response_msg = f"{author}, {action} {order['Qty']} {symbol_str} @{price}"
    elif action.startswith("scale_"):
        ratio = action.replace("scale_", "") # 25, 50, 75, 100
        ratio_str = {"25": "1/4", "50": "1/2", "75": "3/4", "100": "all"}.get(ratio, "all")
        pattern = r"(STC|BTC|BTO|STO)\s+(\d+)?\s+([A-Z0-9_]+)"
        match = re.search(pattern, msg_str)
        if match:
            act, old_qty, sym = match.groups()
            response_msg = msg_str.replace(f"{act} {old_qty if old_qty else ''}", f"{act} {ratio_str}")
        else:
            response_msg = msg_str.replace("STC ", f"STC {ratio_str} ").replace("BTC ", f"BTC {ratio_str} ")
            
    return web.json_response({"success": True, "message": response_msg or msg_str})

async def handle_reconcile(request):
    if bksession is None:
        return web.json_response({"success": False, "error": "No brokerage connected"})
    try:
        msg = alistner.trader.reconcile_portfolio()
        return web.json_response({"success": True, "report": msg})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})

# Helper functions for Quick Alert parser logic
def split_alert_message(gui_msg):
    if len(gui_msg.split(',')) > 2:
        splt = gui_msg.split(',')
        return splt[0], ",".join(splt[1:])
    elif len(gui_msg.split(',')) == 2:
        return gui_msg.split(',')
    elif len(gui_msg.split(':')) == 2:
        return gui_msg.split(':')
    elif len(gui_msg.split(':')) > 2:
        splt = gui_msg.split(':')
        return splt[0], ":".join(splt[1:])
    return "author", gui_msg

def match_authors(author_str: str) -> str:
    if "#" in author_str:
        return author_str
    authors = []
    for chn in channel_ids.keys():
        csv_p = os.path.join(cfg['general']['data_dir'], f"{chn}_message_history.csv")
        if os.path.exists(csv_p):
            try:
                at = pd.read_csv(csv_p)["Author"].unique()
                authors.extend(at)
            except Exception:
                pass
    authors = list(dict.fromkeys(authors))
    authors += cfg['discord']['authors_subscribed'].split(',')
    authors = [a for a in authors if author_str.lower() in str(a).lower()]
    return author_str if not authors else authors[0]

def get_live_quotes_price(symbol, max_delay=2):
    dir_quotes = cfg['general']['data_dir'] + '/live_quotes'
    fquote = f"{dir_quotes}/{symbol}.csv"
    if not os.path.exists(fquote):
        if alistner:
            return alistner.tracker.price_now(symbol, "both") or (None, None)
        return None, None
        
    try:
        with open(fquote, "r") as f:
            quotes = f.readlines()
        tmp = quotes[-1].split(',')
        if len(tmp) == 3:
            timestamp, bid, ask = tmp
        else:
            timestamp, ask = tmp
            bid = ask
        ask = float(ask.strip())
        bid = float(bid.strip())
        return ask, bid
    except Exception:
        if alistner:
            return alistner.tracker.price_now(symbol, "both") or (None, None)
        return None, None

# WebSocket Connection Handler
async def handle_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    active_websockets.add(ws)
    try:
        async for msg in ws:
            pass # Keep alive connection active
    finally:
        active_websockets.discard(ws)
    return ws

# Static routes
async def handle_index(request):
    package_dir = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(package_dir, 'templates', 'index.html')
    if os.path.exists(path):
        return web.FileResponse(path)
    return web.Response(text="templates/index.html not found", status=404)

async def handle_css(request):
    package_dir = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(package_dir, 'templates', 'index.css')
    if os.path.exists(path):
        return web.FileResponse(path, headers={"Content-Type": "text/css"})
    return web.Response(text="templates/index.css not found", status=404)

async def handle_js(request):
    package_dir = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(package_dir, 'templates', 'app.js')
    if os.path.exists(path):
        return web.FileResponse(path, headers={"Content-Type": "application/javascript"})
    return web.Response(text="templates/app.js not found", status=404)

# Discord Bot Client thread runner
def run_client():
    token = get_discord_token()
    if len(token) < 20:
        str_prt = "Discord token not provided in config.ini. Scraper bot will not receive live discord alerts."
        print(str_prt)
        trade_events.put([str_prt, "", "red"])
        return
    try:
        alistner.run(token)
    except Exception as e:
        str_prt = f"Discord bot failed to start: {e}"
        print(str_prt)
        trade_events.put([str_prt, "", "red"])

# Server startup wrapper
def run_web_gui():
    global bksession, alistner, loop
    
    print("\n=======================================================")
    print("      Starting DiscordAlertsTrader Web Server UI       ")
    print("=======================================================\n")
    
    bksession = get_brokerage()
    alistner = DiscordBot(trade_events, brokerage=bksession, cfg=cfg)
    
    # Start Scraper Bot
    client_thread = threading.Thread(target=run_client, daemon=True)
    client_thread.start()
    
    # Configure Server App
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/index.css', handle_css)
    app.router.add_get('/app.js', handle_js)
    app.router.add_get('/ws', handle_ws)
    
    # REST API endpoints
    app.router.add_post('/api/portfolio', handle_portfolio)
    app.router.add_post('/api/tracker', handle_tracker)
    app.router.add_post('/api/stats', handle_stats)
    app.router.add_get('/api/strategy_exits', handle_strategy_exits)
    app.router.add_post('/api/msg_history', handle_msg_history)
    app.router.add_post('/api/dashboard', handle_dashboard)
    app.router.add_get('/api/dashboard/chart', handle_dashboard_chart)
    app.router.add_get('/api/account', handle_account)
    app.router.add_get('/api/config', handle_config_get)
    app.router.add_post('/api/config/save', handle_config_save)
    
    # Quick trades API
    app.router.add_post('/api/quick_trade/trigger', handle_quick_trade_trigger)
    app.router.add_post('/api/quick_trade/action', handle_quick_trade_action)
    app.router.add_post('/api/quick_trade/reconcile', handle_reconcile)
    
    # Start loop background parser task
    async def start_background_tasks(app):
        app['poll_task'] = asyncio.create_task(poll_trade_events())
        
    async def cleanup_background_tasks(app):
        app['poll_task'].cancel()
        await app['poll_task']
        if alistner:
            alistner.close_bot()
            
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    # Open default browser 1.5 seconds after start
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:5002")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Launch server
    web.run_app(app, host='127.0.0.1', port=5002)

if __name__ == '__main__':
    run_web_gui()
