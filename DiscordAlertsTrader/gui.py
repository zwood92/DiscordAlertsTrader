#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr  3 18:18:43 2021

@author: adonay
"""
import os
import os.path as op
import threading
import pandas as pd
from datetime import datetime
import time
import re
import queue
import PySimpleGUIQt as sg
# from PySide2.QtWidgets import QHeaderView
import matplotlib.pyplot as plt

from DiscordAlertsTrader.brokerages import get_brokerage
from DiscordAlertsTrader import gui_generator as gg
from DiscordAlertsTrader import gui_layouts as gl
from DiscordAlertsTrader.discord_bot import DiscordBot
from DiscordAlertsTrader.configurator import cfg, channel_ids
from DiscordAlertsTrader.message_parser import parse_trade_alert, ordersymb_to_str
# A fix for Macs
os.environ['QT_MAC_WANTS_LAYER'] = '1'


def match_authors(author_str:str)->str:
    """Author have an identifier in discord, it will try to find full author name

    Parameters
    ----------
    author_str : str
        string to match the author

    Returns
    -------
    str
        author with identifier
    """
    if "#" in author_str:
        return author_str
    authors = []
    for chn in channel_ids.keys():
        at = pd.read_csv(op.join(cfg['general']['data_dir'] , f"{chn}_message_history.csv"))["Author"].unique()
        authors.extend(at)
    authors = list(dict.fromkeys(authors))
    
    authors += cfg['discord']['authors_subscribed'].split(',')
    authors = [a for a in authors if author_str.lower() in a.lower()]
    if len(authors) == 0:
        author = author_str
    elif len(authors) > 1:
        author = author_str
    else:
        author = authors[0]
    return author

def split_alert_message(gui_msg):
    # extra comas
    if len(gui_msg.split(','))>2:
        splt = gui_msg.split(',')
        author = splt[0]
        msg = ",".join(splt[1:])
    # one coma
    elif len(gui_msg.split(','))==2:
        author, msg = gui_msg.split(',')
    # one colon
    elif len(gui_msg.split(':'))==2:
        author, msg = gui_msg.split(':')
    # extra colons
    elif len(gui_msg.split(':'))>2:
        splt = gui_msg.split(':')
        author = splt[0]
        msg = ":".join(splt[1:])
        
    # no colon or coma
    else:
        print("No colon or coma in message, author not found, assuming no author")
        author = "author"
        msg = gui_msg
    return author, msg

def get_live_quotes(symbol, tracker, max_delay=2):
    dir_quotes = cfg['general']['data_dir'] + '/live_quotes'
    
    fquote = f"{dir_quotes}/{symbol}.csv"
    if not op.exists(fquote):
        quote = tracker.price_now(symbol, "both")
        if quote is None:
            return None, None        
        return quote
    
    with open(fquote, "r") as f:
        quotes = f.readlines()
    
    now = time.time()
    get_live = False
    try:
        tmp = quotes[-1].split(',') # in s  
        if len(tmp) == 3:
            timestamp, bid, ask = tmp
        else:
            timestamp, ask = tmp
            bid = ask
        ask = ask.strip().replace('\n', '')
        quote = [ask, bid]
    except:
        print("Error reading quote", symbol, quotes[-1])
        get_live = True
    
    timestamp = eval(timestamp)
    if max_delay is not None:
        if now - timestamp > max_delay:
            get_live = True
    
    if get_live:
        quote = tracker.price_now(symbol, "both")
        if quote is None:
            return None, None        
        return quote
    return quote


def quotes_plotting(symbol, trader=None, tracker=None):
    dir_quotes = cfg['general']['data_dir'] + '/live_quotes'
    
    fquote = f"{dir_quotes}/{symbol}.csv"
    if not op.exists(fquote):      
        return None
    
    quotes = pd.read_csv(fquote)
    
    quotes['date'] = pd.to_datetime(quotes['timestamp'], unit='s', utc=True).dt.tz_convert('America/New_York')
    quotes['date'] = quotes['date'].dt.tz_localize(None)
    quotes['ask'] = quotes[' quote_ask']
    quotes['bid'] = quotes[' quote']

    quotes = quotes[quotes['date'].dt.date == datetime.now().date()]
    quotes = quotes[quotes['ask'] > 0]
    quotes.set_index('date', inplace=True)
    
    quotes[['ask', 'bid']].plot(alpha=0.5)
    
    for tt in [trader, tracker]:
        if tt is not None:
            tts  = tt.portfolio[(tt.portfolio['Symbol'] == symbol) &
                                (pd.to_datetime(tt.portfolio['Date']).dt.date == datetime.now().date()) ]
            if len(tts):
                for ix, row in tts.iterrows():
                    if str(tt.__class__) == "<class 'DiscordAlertsTrader.alerts_tracker.AlertsTracker'>":                        
                        plt.plot(pd.to_datetime(row['Date']), row['Price'], 'go')
                        plt.text(pd.to_datetime(row['Date']), row['Price']*1.009, f"track:{row['Trader']}: {row['Type']}", fontsize=12, color='g', rotation=45)
                        if not pd.isna(row['STC-Date']):
                            plt.plot(pd.to_datetime(row['STC-Date']), row['STC-Price'], 'ro')
                            plt.text(pd.to_datetime(row['STC-Date']), row['STC-Price']*1.009, f"track:{row['Trader']}: Closed", fontsize=12, color='red', rotation=45)
                    else:
                        plt.plot(pd.to_datetime(row['Date']), row['Price'], 'go')
                        plt.plot(pd.to_datetime(row['Date']), row['Price'], 'kx')
                        plt.text(pd.to_datetime(row['Date']), row['Price']*1.009, f"port:{row['Trader']} {row['Type']}", fontsize=12, color='g', rotation=45)
                        cols = [c for c in tts.columns if c.startswith('STC') and c.endswith('-Date')]
                        for c in cols:
                            if pd.isna(row[c]):
                                continue
                            print(row[c])
                            plt.plot(pd.to_datetime(row[c]), row[c.split("-")[0] + '-Price'], 'ro')
                            plt.plot(pd.to_datetime(row[c]), row[c.split("-")[0] + '-Price'], 'kx')
                            plt.text(pd.to_datetime(row[c]), row[c.split("-")[0] + '-Price']*1.009, f"port:{row['Trader']}: Closed", fontsize=12, color='red', rotation=45)
    plt.tight_layout()
    plt.title(symbol)
    plt.show(block=False)


def fit_table_elms(Widget_element):
    Widget_element.resizeRowsToContents()
    Widget_element.resizeColumnsToContents()
    Widget_element.resizeRowsToContents()
    Widget_element.resizeColumnsToContents()

# sg.theme('Dark Blue 3')
sg.theme('DarkGrey8')
sg.SetOptions(font=("Helvetica", 12))

fnt_b = ("Helvetica", 11)
fnt_h = ("Helvetica", 12, "bold")

ly_cons, MLINE_KEY = gl.layout_console('Discord messages from all the channels', '-MLINE-')
ly_cons_subs, MLINE_SUBS_KEY = gl.layout_console('Discord messages only from subscribed authors',
                                       '-MLINEsub-')

print(1)
gui_data = {}
gui_data['port'] = gg.get_portf_data()
ly_port = gl.layout_portfolio(gui_data['port'], fnt_b, fnt_h)

gui_data['trades'] = gg.get_tracker_data()
ly_track = gl.layout_traders(gui_data['trades'], fnt_b, fnt_h)

gui_data['stats'] = gg.get_stats_data()
ly_stats = gl.layout_stats(gui_data['stats'], fnt_b, fnt_h)
print(2)

chns = list(channel_ids.keys())
gui_data['_msg_hist_'] = gg.get_hist_msgs(chan_name=chns[0] if chns else None)
msg_tab = gl.layout_chan_msg(chns, gui_data['_msg_hist_'], fnt_b, fnt_h)

ly_dash = gl.layout_dashboard(gui_data['port'], gui_data['trades'], gui_data['stats'])

bksession = get_brokerage()
ly_accnt = gl.layout_account(bksession, fnt_b, fnt_h)
ly_conf = gl.layout_config(fnt_b, cfg)

tab_group_layout = [
    [sg.Tab("Dashboard", ly_dash, font=fnt_b)],
    [sg.Tab("Msgs Subs", ly_cons_subs, font=fnt_b)],
    [sg.Tab("Msgs All", ly_cons, font=fnt_b)], 
    [sg.Tab('Portfolio', ly_port)],
    [sg.Tab('Analysts Portfolio', ly_track)],
    [sg.Tab('Analysts Stats', ly_stats)],
    [sg.Tab('Msg History', msg_tab)],                        
    [sg.Tab("Account", ly_accnt)],
    [sg.Tab("Config", ly_conf)]
]

side_panel = gl.layout_side_panel()

layout = [
    [
        sg.Column([[sg.TabGroup(tab_group_layout, title_color='black', font=fnt_b, key="-TAB-GROUP-")]]),
        sg.VerticalSeparator(),
        sg.Column(side_panel, background_color="#252526", pad=(10, 0))
    ]
]
print(3)
bk_name = "None" if bksession is None else bksession.name
window = sg.Window(f'Discord Alerts Trader - with broker {bk_name}', layout,size=(1400, 800), # force_toplevel=True,
                    auto_size_text=True, resizable=True)
print(4)
def mprint_queue(queue_item_list, subscribed_author=False):
    # queue_item_list = [string, text_color, background_color]
    kwargs = {}
    text = queue_item_list[0]
    len_que = len(queue_item_list)
    if len_que == 2:
        kwargs["text_color"] = queue_item_list[1]
    elif len_que == 3:
        tcol = queue_item_list[1]
        tcol = "white" if tcol == "" else tcol
        if tcol.lower() == "blue":
            tcol = "white"
        kwargs["text_color"] = tcol

        bcol = queue_item_list[2]
        bcol = "#1e1e1e" if bcol == "" else bcol
        if bcol == "white":
            bcol = "#1e1e1e"
        kwargs["background_color"] = bcol

    window[MLINE_KEY].print(text, **kwargs)
    if subscribed_author or len_que == 3:
        window[MLINE_SUBS_KEY].print(text, **kwargs)

def update_portfolios_thread(window):
    while True:
        time.sleep(60)
        try:
            window.write_event_value("_upd-portfolio_", None)
            time.sleep(2)  
            window.write_event_value("_upd-track_", None)
            time.sleep(2)
            window.write_event_value("_upd-dash_", None)
        except AttributeError:
            pass
print(5)
event, values = window.read(.1)

els = ['_portfolio_', '_track_', '_msg_hist_table_']
els = els + ['_orders_', '_positions_'] if bksession is not None else els
for el in els:
    try:
        fit_table_elms(window.Element(el).Widget)
    except:
        pass

print(6)
event, values = window.read(.1)
print(7)
trade_events = queue.Queue(maxsize=20)
alistner = DiscordBot(trade_events, brokerage=bksession, cfg=cfg)
print(8)
threading.Thread(target=update_portfolios_thread, args=(window,), daemon=True).start()
print(9)
event, values = window.read(.1)

# exclusion filters for the portfolio and analysts tabs
port_exc = {"Closed":False,
            "Open":False,
            "NegPnL":False,
            "PosPnL":False,
            "live PnL":False,
            "stocks":True,
            "options":False,
            'bto':False,
            "stc":False,
            }
track_exc = port_exc.copy()
stat_exc = port_exc.copy()
port_exc["Canceled"] = True
port_exc["Rejected"] = False

print(10)
dt, _  = gg.get_tracker_data(track_exc, **values)
window.Element('_track_').Update(values=dt)
fit_table_elms(window.Element("_track_").Widget)
dt, hdr = gg.get_portf_data(port_exc)
window.Element('_portfolio_').Update(values=dt)
fit_table_elms(window.Element("_portfolio_").Widget)
dt, hdr = gg.get_stats_data(stat_exc)
window.Element('_stat_').Update(values=dt)
fit_table_elms(window.Element("_stat_").Widget)


def run_gui():  
    subs_auth_msg = False
    auth_subs = cfg['discord']['authors_subscribed'].split(',')
    auth_subs = [i.split("#")[0].strip() for i in auth_subs]
    ori_color = 'black'
    
    # Initial Dashboard update
    try:
        window.write_event_value("_upd-dash_", None)
    except AttributeError:
        pass

    while True: 
        event, values = window.read(1)#.1)

        if event == sg.WINDOW_CLOSED:
            break

        # Prefill trigger alert message
        if ('_portfolio_' in event and values['_portfolio_'] != []) or \
            ('_track_' in event and values['_track_'] != []):  
            if '_portfolio_' in event:
                pix = values['_portfolio_'][0] 
                dt, hdr = gg.get_portf_data(port_exc, **values)
                if len(dt) and len(dt) > pix:
                    qty = dt[pix][hdr.index('filledQty')]
                else:
                    qty = ""
            else:
                pix = values['_track_'][0]
                dt, hdr = gg.get_tracker_data(track_exc, **values)
                qty = dt[pix][hdr.index('Qty')]  
            qty = qty if qty == "" else int(float(qty)) 
            window["-MANUAL-QTY-"].update(qty)
            try:
                symb = dt[pix][hdr.index('Symbol')]
            except: 
                continue   
            auth = match_authors(dt[pix][hdr.index('Trader')])
            
            price = ""
            if "Live" in hdr:
                price = dt[pix][hdr.index('Live')]
            if price == "":
                try:
                    price = dt[pix][hdr.index('STC-Price-actual')]
                except:
                    price = ""
            if price == "":
                try:
                    price = dt[pix][hdr.index('STC-Price')]
                except:
                    price = "0"
            if 'Type' in hdr:
                action = dt[pix][hdr.index('Type')]
                if action == "BTO":
                    action = "STC"
                elif action == "STO":
                    action = "BTC"
            else:
                action = "STC"
            price = price if price == "" else float(price)
            if "_" in symb:
                # option
                exp = r"(\w+)_(\d{6})([CP])([\d.]+)"        
                match = re.search(exp, symb, re.IGNORECASE)
                if match:
                    symbol, date, type, strike = match.groups()
                    symb_str = f"{auth}, {action} {qty} {symbol} {strike}{type} {date[:2]}/{date[2:4]} @{price}"
            else:
                symb_str= f"{auth}, {action} {qty} {symb} @{price}"
            window.Element("-subm-msg").Update(value=symb_str)
            try:
                window["-SIDE-CURRENT-TRADE-"].update(f"{action} {qty} {symb} @ {price}\nAuthor: {auth}")
            except:
                pass
        # handle alert buttons
        elif event == '-toggle':
            state = window[event].GetText()
            butts = ['-alert_to-', '-alert_BTO', '-alert_STC', '-alert_STO', '-alert_BTC', '-alert_exitupdate',
                     '-alert_quotes', '-alert_plot', '-alert_tome', '-alert_tomeshort', '-alert_exits' ]
            if state == '▲':
                window[event].update(text='▼')            
            else:
                window[event].update(text='▲')
            for el in butts:
                window[el].update(visible=state == '▲')
                
        elif event.startswith('-alert_' ):
            print(event)
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()            

            action = event.split('_')[1]
            
            msg_split = split_alert_message(values['-subm-msg'])
            if len(msg_split) == 2:
                author, alert = msg_split
            else:
                author, alert = "author", msg_split[0]
            
            if event.startswith('-alert_tome'):
                author = "me" if event == '-alert_tome' else "me_short"
                msg = f"{author}, {alert.strip()}"
                window.Element("-subm-msg").Update(value=msg)
                window.Element(event).Update(button_color=ori_col)
                continue   

            # Use manual qty if provided
            manual_qty = values.get("-MANUAL-QTY-", "")
            
            # fix missing price, none price, no action
            if "@" not in alert:
                alert += " @0.01"
            
            # Update qty in message if manual_qty is set
            pattern = r"(BTO|STO|STC|BTC)\s+(\d+)?\s+([A-Z0-9_]+)"
            match = re.search(pattern, alert)
            if match and manual_qty:
                act, old_qty, symbol = match.groups()
                alert = alert.replace(f"{act} {old_qty if old_qty else ''}", f"{act} {manual_qty}")
            if  not len([p for p in ["BTO", "STO", "BTC", "STC"] if p in alert]):
                alert = "BTO " + alert                
            alert = alert.replace("@None", "@0.01").replace("@m", "@0.01")
            _, order = parse_trade_alert(alert)

            if order is None:
                window.Element(event).Update(button_color=ori_col)
                continue
            
            if '-alert_plot' in event:
                # get live quotes and plot
                quotes_plotting(order['Symbol'], alistner.trader, alistner.tracker)
                window.Element(event).Update(button_color=ori_col)
                continue
            
            ask, bid = get_live_quotes(order['Symbol'], alistner.tracker)
            if action in ["BTO", "BTC"] or order['action'] in ["BTO", "BTC"]:
                price = ask
            elif action in ["STO", "STC"] or order['action'] in ["STO", "STC"]:
                price = bid
            else:
                price = ask
            if price is None:
                price = order.get('price', 0.01)
            symbol = ordersymb_to_str(order['Symbol'])
            if order.get('Qty') is None:
                order['Qty'] = 1
            if action =='exitupdate':
                msg =  f"{author}, Exit Update {symbol} PT 50% SL 50%"
            elif action == 'exits':
                msg =  f"{author}, Exit Update {symbol} PT1 20% PT2 40% PT3 60% SL 50%"
            elif action == 'quotes': 
                action_msg = order['action'].replace('ExitUpdate', "BTO")
                
                msg =  f"{author}, {action_msg} {order['Qty']} {symbol} @{price} | [ask {ask} bid {bid}]" 
            else:
                msg =  f"{author}, {action} {order['Qty']} {symbol} @{price}" 
                
            window.Element("-subm-msg").Update(value=msg)
            window.Element(event).Update(button_color=ori_col)
            
        elif event == "_upd-portfolio_": # update button in portfolio
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            dt, _ = gg.get_portf_data(port_exc, **values)
            window.Element('_portfolio_').Update(values=dt)
            fit_table_elms(window.Element("_portfolio_").Widget)
            window.Element(event).Update(button_color=ori_col)

            
        elif event == "cfg_button":
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            for k, v in values.items():
                if k.startswith("cfg"):
                    if isinstance(window[k], sg.Checkbox):
                        continue
                    if window.Element(k).TextColor == 'red':
                        window.Element(k).Update(text_color=ori_color)
                    f1,f2 = k.replace("cfg_", "").split(".")
                    cfg[f1][f2] = str(v)
            window.Element(event).Update(button_color=ori_col)

        elif event.startswith("cfg"):
            # print(event)
            if isinstance(window[event], sg.Checkbox):
                f1,f2 = event.replace("cfg_", "").split(".")
                # print("before", cfg[f1][f2])
                cfg[f1][f2] = str(values[event])
                print("changed", cfg[f1][f2])
            else:
                cur_color = window.Element(event).TextColor
                if cur_color != "red":
                    ori_color = cur_color
                window.Element(event).Update(text_color="red")
            
        elif event == "_upd-track_": # update button in analyst alerts
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            dt, _  = gg.get_tracker_data(track_exc, **values)
            window.Element('_track_').Update(values=dt)
            fit_table_elms(window.Element("_track_").Widget)
            window.Element(event).Update(button_color=ori_col)

        elif event == "_upd-stat_": # update button in analyst stats
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            dt, _  = gg.get_stats_data(stat_exc, **values)
            window.Element('_stat_').Update(values=dt)
            fit_table_elms(window.Element("_stat_").Widget)
            window.Element(event).Update(button_color=ori_col)
            window.write_event_value("_upd-dash_", None)

        elif event in ("_msg_hist_UPD_", "_msg_hist_chn_"): # update button in msg history
            if event == "_msg_hist_UPD_":
                ori_col = window.Element(event).ButtonColor
                window.Element(event).Update(button_color=("black", "white"))
                window.refresh()
            
            chn = values['_msg_hist_chn_']
            kwargs = {
                'filt_author': values.get('_msg_hist_filt_author_'),
                'filt_date_frm': values.get('_msg_hist_filt_date_frm_'),
                'filt_date_to': values.get('_msg_hist_filt_date_to_'),
                'filt_cont': values.get('_msg_hist_filt_cont_')
            }
            dt, _ = gg.get_hist_msgs(chan_name=chn, **kwargs)
            window.Element('_msg_hist_table_').Update(values=dt)
            fit_table_elms(window.Element("_msg_hist_table_").Widget)
            
            if event == "_msg_hist_UPD_":
                window.Element(event).Update(button_color=ori_col)

        elif event == "-DASH-TIMEFRAME-":
            window.write_event_value("_upd-dash_", None)

        elif event == "_upd-dash_":
            timeframe = window["-DASH-TIMEFRAME-"].get() if "-DASH-TIMEFRAME-" in window.AllKeysDict else "This Month"
            metrics = gg.get_dashboard_metrics(gui_data['port'], gui_data['trades'], gui_data['stats'], timeframe=timeframe)
            
            pnl_val = metrics["total_pnl"]
            pnl_color = "#00ff00" if not pnl_val.startswith("$-") and pnl_val != "$0.00" else ("#ff3333" if pnl_val.startswith("$-") else "white")
            window["-DASH-TOTAL-PNL-"].update(pnl_val, text_color=pnl_color)
            
            window["-DASH-WIN-RATE-"].update(metrics["win_rate"])
            window["-DASH-TOTAL-TRADES-"].update(metrics.get("total_trades", "0"))
            window["-DASH-RECENT-TAB-"].update(values=metrics["recent_performance"])
            
            if metrics.get("chart_path") and op.exists(metrics["chart_path"]):
                window["-DASH-EQUITY-CHART-"].update(filename=metrics["chart_path"])
            else:
                window["-DASH-EQUITY-CHART-"].update(data=b"")
            
            # Status update
            bot_status = "ACTIVE" if alistner.is_alive() else "STOPPED"
            window["-DASH-BOT-STATUS-"].update(bot_status, text_color="#00ff00" if bot_status == "ACTIVE" else "#ff3333")
            
            # Update sentiment from recent analyst alerts
            if not alistner.tracker.portfolio.empty:
                last_alert = alistner.tracker.portfolio.iloc[-1]
                if last_alert['isOpen'] == 1:
                    window["-SENTIMENT-"].update("BULLISH" if last_alert['Type'] == "BTO" else "BEARISH")
                    window["-SENTIMENT-"].update(text_color="green" if last_alert['Type'] == "BTO" else "red")
                    window["-RATIONALE-"].update(f"Analyst {last_alert['Trader']} opened {last_alert['Symbol']} @ {last_alert['Price']}")

        elif event == "-SIDE-RECONCILE-":
            if bksession:
                # Assuming alistner has trader and tracker
                msg = alistner.trader.reconcile_portfolio()
                sg.popup(msg, title="Reconciliation Results")
            else:
                sg.popup("No brokerage connected", title="Error")

        elif event in ["-SCALE-25-", "-SCALE-50-", "-SCALE-75-", "-SCALE-100-"]:
            cur_msg = values['-subm-msg']
            if "STC" not in cur_msg and "BTC" not in cur_msg:
                sg.popup("Please select an open position first.", title="Notice")
                continue
            
            if event == "-SCALE-25-": ratio = "1/4"
            elif event == "-SCALE-50-": ratio = "1/2"
            elif event == "-SCALE-75-": ratio = "3/4"
            else: ratio = "all"
            
            # Replace quantity in message with ratio
            # Regex to find action and quantity: action (qty)? symbol
            pattern = r"(STC|BTC|BTO|STO)\s+(\d+)?\s+([A-Z0-9_]+)"
            match = re.search(pattern, cur_msg)
            if match:
                action, qty, symbol = match.groups()
                new_msg = cur_msg.replace(f"{action} {qty if qty else ''}", f"{action} {ratio}")
                window["-subm-msg"].update(new_msg)
            else:
                # Fallback simple replace
                window["-subm-msg"].update(cur_msg.replace("STC ", f"STC {ratio} ").replace("BTC ", f"BTC {ratio} "))

        elif event.startswith("-port-"): # radial click, update portfolio
            key =  event.replace("-port-", "")
            state = window.Element(event).get()
            port_exc[key] = state
            dt, _ = gg.get_portf_data(port_exc, **values)
            window.Element('_portfolio_').Update(values=dt)

        elif event.startswith("-track-"): # radial click, update analyst alerts
            key =  event.replace("-track-", "")
            state = window.Element(event).get()
            track_exc[key] = state
            dt, _ = gg.get_tracker_data(track_exc, **values)
            window.Element('_track_').Update(values=dt)

        elif event.startswith("-stat-"): # radial click, update analyst stats
            key =  event.replace("-stat-", "")
            state = window.Element(event).get()
            stat_exc[key] = state
            dt, _ = gg.get_stats_data(stat_exc, **values)
            window.Element('_stat_').Update(values=dt)

        elif False:  # Old per-channel UPD handler removed
            pass

        elif event == 'acc_updt':
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            gl.update_acct_ly(bksession, window)
            fit_table_elms(window.Element(f"_positions_").Widget)
            fit_table_elms(window.Element(f"_orders_").Widget)
            window.Element(event).Update(button_color=ori_col)

        elif event == "-subm-alert":
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()    
            try:        
                author,msg = split_alert_message(values['-subm-msg'])
                author = match_authors(author.strip())
                msg = msg.strip().replace("SPXW", "SPX")
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                chan = "GUI_" + values["_chan_trigg_"]
                print(chan)
                new_msg = pd.Series({
                    'AuthorID': None,
                    'Author': author,
                    'Date': date, 
                    'Content': msg,
                    'Channel': chan
                    })
                alistner.new_msg_acts(new_msg, from_disc=False)
                window.Element(event).Update(button_color=ori_col)
            except Exception as e:
                print("Trigger alerts with error:", e)
                window.Element(event).Update(button_color=ori_col)
                continue

        try:
            event_feedb = trade_events.get(False)
            # if message from subscribed author or channel flag it to print in both consoles
            if event_feedb[1] == "blue":
                author = event_feedb[0].split("\n\t")[1].split(":")[0]
                chan = event_feedb[0].split(": \n\t")[0].split(" ")[-1]
                if any(a == author for a in auth_subs):
                    subs_auth_msg = True
                elif cfg['discord']['channelwise_subscription'].split(",") != [""] and \
                    any([c.strip() == chan for c in cfg['discord']['channelwise_subscription'].split(",")]):
                    subs_auth_msg = True
                elif cfg['discord']['authorwise_subscription'].split(",") != [""] and \
                    any([c.strip() == author for c in cfg['discord']['authorwise_subscription'].split(",")]):
                    subs_auth_msg = True
                else:
                    subs_auth_msg = False
            
            mprint_queue(event_feedb, subs_auth_msg)
        except queue.Empty:
            pass


def run_client():
    if len(cfg['discord']['discord_token']) < 50:
        str_prt = "Discord token not provided, no discord messages will be received. Add user token in config.ini"
        print(str_prt)
        time.sleep(3)
        trade_events.put([str_prt,"", "red"])
        return
    alistner.run(cfg['discord']['discord_token'])


def gui():   
    client_thread = threading.Thread(target=run_client, daemon=True)

    # start the threads
    client_thread.start()
    run_gui()

    # close the GUI window
    window.close()
    alistner.close_bot()
    exit()


if __name__ == '__main__':
    gui()
