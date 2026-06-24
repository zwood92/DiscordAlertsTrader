#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 27 11:54:36 2021

@author: adonay
"""
import os
import pandas as pd
import PySimpleGUIQt as sg
from . import gui_generator as gg
from .configurator import cfg, channel_ids

_analyst_list = ['All'] + list(channel_ids.keys())


tip = "coma separed patterns, e.g. string1,string2"
tlp_date = "Date can be:\n-a date mm/dd/yyyy, mm/dd\n-a period: today, yesterday, week, biweek, month, mtd, ytd"

def layout_console(ttl='Discord messages from subscribed channels', 
                   key='-MLINE-__WRITE ONLY__'):
    layout = [[sg.Text(ttl, font=("Helvetica", 14, "bold"), size=(100,1))],
              [sg.Multiline(size=(180, 32), key=key, autoscroll=True, enable_events=False, 
                           font=("Courier New", 11), background_color="#1e1e1e", text_color="#d4d4d4")]]
    return layout, key

def layout_console_subs(ttl='Discord messages only from subscribed authors', 
                        key='-MLINEsub-', authors_list=[]):
    layout = [
        [
            sg.Text(ttl, font=("Helvetica", 14, "bold")),
            sg.Stretch(),
            sg.Text("Filter Analyst: ", font=("Helvetica", 11)),
            sg.Combo(["All Subscribed"] + authors_list, default_value="All Subscribed", 
                     key="-FILTER-SUBSCRIBED-ANALYST-", enable_events=True, size=(25, 1))
        ],
        [
            sg.Multiline(size=(180, 32), key=key, autoscroll=True, enable_events=False, 
                         font=("Courier New", 11), background_color="#1e1e1e", text_color="#d4d4d4")
        ]
    ]
    return layout, key

def layout_dashboard(port_data, track_data, stats_data):
    def card(title, key, tooltip, color="#2d2d2d"):
        return sg.Frame('', [[
            sg.Column([
                [sg.Text(title, font=("Helvetica", 11, "bold"), text_color="#a0a0a0", tooltip=tooltip)],
                [sg.Text("---", font=("Helvetica", 22, "bold"), key=key, text_color="white", size=(12, 1), justification='center')]
            ], background_color=color, pad=(15, 10), element_justification='center')
        ]], background_color=color, border_width=1, pad=(5, 5))

    layout = [
        [
            sg.Text("Trading Dashboard", font=("Helvetica", 20, "bold"), pad=((0, 20), (10, 20))),
            sg.Stretch(),
            sg.Text("Timeframe: ", font=("Helvetica", 12)),
            sg.Combo(["Today", "This Week", "This Month", "All Time"], default_value="This Month", key="-DASH-TIMEFRAME-", enable_events=True, size=(15, 1), font=("Helvetica", 12))
        ],
        [
            card("Total PnL", "-DASH-TOTAL-PNL-", "Total cumulative Profit and Loss in dollars."),
            card("Win Rate", "-DASH-WIN-RATE-", "Percentage of winning trades out of total trades."),
            card("Total Trades", "-DASH-TOTAL-TRADES-", "Total number of closed trades."),
            card("Bot Status", "-DASH-BOT-STATUS-", "Current status of the background discord scraper bot.", color="#1e1e1e"),
        ],
        [sg.HorizontalSeparator(pad=(0, 15))],
        [
            sg.Column([
                [sg.Text("Equity Curve", font=("Helvetica", 14, "bold"))],
                [sg.Image(key="-DASH-EQUITY-CHART-", background_color="#2c2c2c", size=(600, 300))]
            ], element_justification='center', pad=(10, 10)),
            sg.Column([
                [sg.Frame("Analyst Sentiment Radar", [
                    [sg.Text("Market Sentiment:", font=("Helvetica", 11)), sg.Text("Neutral", key="-SENTIMENT-", text_color="yellow", font=("Helvetica", 11, "bold"))],
                    [sg.Text("Trade Rationale:", font=("Helvetica", 10))],
                    [sg.Multiline("No recent rationale available.", key="-RATIONALE-", size=(40, 4), disabled=True, background_color="#2c2c2c", text_color="white")]
                ], border_width=1, pad=(0, 10))],
                [sg.Text("Top Analysts", font=("Helvetica", 14, "bold"))],
                [sg.Table(values=[["No Data", "", ""]], headings=["Analyst", "Trades", "Win %"], 
                         auto_size_columns=True, key="-DASH-RECENT-TAB-", num_rows=5, 
                         header_font=("Helvetica", 10, "bold"), font=("Helvetica", 10), alternating_row_color='#333333')]
            ], element_justification='left', pad=(20, 10))
        ]
    ]
    return layout

def layout_side_panel():
    tp_chan = "Select portfolios to trigger alert"
    layout = [
        [sg.Text("QUICK TRADE", font=("Helvetica", 14, "bold"), text_color="#00ff00")],
        [sg.Text("Portfolio:"), sg.Combo(['both', 'user', 'analysts'], default_value='analysts', key="_chan_trigg_", size=(15, 1))],
        [sg.Frame("Current Trade", [
            [sg.Text("No trade selected", key="-SIDE-CURRENT-TRADE-", size=(25, 2), font=("Helvetica", 10), text_color="cyan")]
        ], border_width=1, pad=(0, 10))],
        [sg.Input(default_text="Select row to prefill...", size=(30, 1), key="-subm-msg")],
        [sg.Button("TRIGGER", key="-subm-alert", size=(25, 1), button_color=("white", "#2e7d32"))],
        [sg.HorizontalSeparator(pad=(0, 10))],
        [sg.Text("Actions:")],
        [sg.Button("BTO", key='-alert_BTO', size=(12, 1)), sg.Button("STC", key='-alert_STC', size=(12, 1))],
        [sg.Button("STO", key='-alert_STO', size=(12, 1)), sg.Button("BTC", key='-alert_BTC', size=(12, 1))],
        [sg.HorizontalSeparator(pad=(0, 5))],
        [sg.Text("Manual Scale:")],
        [sg.Input("1", key="-MANUAL-QTY-", size=(5, 1)), sg.Text("Qty")],
        [sg.Button("25%", key="-SCALE-25-", size=(5, 1)), sg.Button("50%", key="-SCALE-50-", size=(5, 1)), 
         sg.Button("75%", key="-SCALE-75-", size=(5, 1)), sg.Button("100%", key="-SCALE-100-", size=(5, 1))],
        [sg.Button("Update SL", key='-alert_exitupdate', size=(25, 1))],
        [sg.Button("Quotes", key='-alert_quotes', size=(12, 1)), sg.Button("Plot", key='-alert_plot', size=(12, 1))],
        [sg.HorizontalSeparator(pad=(0, 10))],
        [sg.Text("Quick Tags:")],
        [sg.Button("me", key='-alert_tome', size=(12, 1)), sg.Button("me_short", key='-alert_tomeshort', size=(12, 1))],
        [sg.HorizontalSeparator(pad=(0, 10))],
        [sg.Button("Reconcile Portfolio", key="-SIDE-RECONCILE-", size=(25, 1), button_color=("white", "#1e3a8a"))],
        [sg.Stretch()]
    ]
    return layout

def trigger_alerts_layout():
    tp_chan = "Select portfolios to trigger alert.\n'user' for your portfolio only. Will bypass false do_BTO and do_BTC and make the trade \n" +\
                "'analysts' for the alerts tracker,\n'all' for both"
    tp_trig = "Click portfolio row number to prefill the STC alert. Alerts can look like\n" +\
                "BTO: Author, BTO 1 AAA 115C 05/30 @2.5 PT 3.5TS30% PT2 4 SL TS40% -> '%' for percentage, TS for Trailing Stop\n" +\
                "STC: Author, STC 1 AAA 115C 05/30 @3\n" +\
                "Exit Update: Author, exit update AAA 115C 05/30 PT 80% SL 2\n" +\
                "Exit Update: Author, exit update AAA 115C 05/30 isopen:no\n"  +\
                "Exit Update: Author, exit update AAA 115C 05/30 cancelAVG\n"  +\
                "Get quotes: Author, BTO 1 AAA 115C 05/30 @m" 
    lay = [[
           sg.Text('to portfolio:', tooltip=tp_chan),
           sg.Combo(['both', 'user', 'analysts'], default_value='analysts', key="_chan_trigg_",tooltip=tp_chan, readonly=True, size=(15,1)),
           
           sg.Button('▲', key='-toggle',   enable_events=True, 
                                 tooltip='Show/hide change alert action'),
            sg.Input(default_text="Author, STC 1 AAA 115C 05/30 @2.5 [click port row number to prefill]",
                    size= (100,1), key="-subm-msg",
                    tooltip=tp_trig),
           sg.Button("Trigger alert", key="-subm-alert", 
                     tooltip="Will generate alert in user or/and analysts portfolio, useful to close or open a position", size= (20,1)),
           sg.Stretch()], 
           [sg.Text('Change alert to:', key='-alert_to-', tooltip="Change  current alert in tigger alert", visible=True),
            sg.Button("BTO", key='-alert_BTO', size=(10,1), tooltip="Once clicked portfolio row change prefilled STC to BTO", visible=True),
            sg.Button("STC", key='-alert_STC', size=(10,1), tooltip="Once clicked portfolio row change prefilled to STC", visible=True),
            sg.Button("STO", key='-alert_STO', size=(10,1), tooltip="Once clicked portfolio row change prefilled STC to BTO", visible=True),
            sg.Button("BTC", key='-alert_BTC', size=(10,1), tooltip="Once clicked portfolio row change prefilled to STC", visible=True),
            sg.Button("ExitUpdate", key='-alert_exitupdate', size=(20,1), tooltip="Once clicked portfolio row change prefilled STC to exit update", visible=True),
            sg.Button("Get quotes", key='-alert_quotes', size=(20,1), tooltip="get quotes from alerts in trigger box. In alert pass prices as @m to get market price", visible=True),
            sg.Button("Plot quotes", key='-alert_plot', size=(20,1), tooltip="plot daily quotes from alerts in trigger box", visible=True),
            sg.Button("author: me", key='-alert_tome', size=(20,1), tooltip="change author in alert to 'me'", visible=True),
            sg.Button("author: me_short", key='-alert_tomeshort', size=(30,1), tooltip="change author in alert to 'me_short'", visible=True),
            sg.Button("3 exits 1 SL", key='-alert_exits', size=(20,1), tooltip="change exits to PT1 20% PT2 40% PT3 60% SL 50%'", visible=True),
            sg.Stretch()
           ]
           ]
    return lay

def layout_portfolio(data_n_headers, font_body, font_header):
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [
         [sg.Column([[
            sg.Text('Include:  Authors: ', auto_size_text=True,tooltip=tip), sg.Listbox(_analyst_list, default_values=['All'], select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, key=f'port_filt_author',tooltip=tip, size=(20,3)),
            sg.Text('Date from: ', tooltip=tlp_date),sg.Combo(['today', 'week', 'month'], default_value='week',
                                                              key=f'port_filt_date_frm', tooltip=tlp_date),
            sg.Text(' To: ', tooltip=tlp_date), sg.Combo(['today', 'week', 'month'], default_value='today',
                                                         key=f'port_filt_date_to', tooltip=tlp_date),
            sg.Text(' Symbols: ', tooltip=tip), sg.Input(key=f'port_filt_sym', tooltip=tip),
            sg.Text(' Channels: ',tooltip=tip), sg.Input(key=f'port_filt_chn',tooltip=tip)
            ],                                        
            [sg.Text("Exclude: |"),
            sg.Checkbox("Closed", key="-port-Closed", enable_events=True),
            sg.Checkbox("Open", key="-port-Open", enable_events=True),
            sg.Checkbox("Canceled", key="-port-Canceled", default=True, enable_events=True),
            sg.Checkbox("Rejected", key="-port-Rejected", default=True, enable_events=True),
            sg.Checkbox("Neg PnL", key="-port-NegPnL", enable_events=True),
            sg.Checkbox("Pos PnL", key="-port-PosPnL", enable_events=True),
            sg.Checkbox("Live PnL", key="-port-live PnL", enable_events=True),
            sg.Checkbox("Stocks", key="-port-stocks", default=True, enable_events=True),
            sg.Checkbox("Options", key="-port-options", enable_events=True),
            sg.Checkbox("BTO", key="-port-bto", enable_events=True),
            sg.Checkbox("STO", key="-port-sto", enable_events=True),
            sg.Text('| Excl Authors: ', auto_size_text=True,tooltip=tip), sg.Listbox(_analyst_list, default_values=[], select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, key=f'port_exc_author', tooltip=tip, size=(20,3)),
            sg.Text('Excl Channels: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'port_exc_chn',tooltip=tip),
            ],
            [sg.ReadButton("Update", button_color=('white', 'black'),bind_return_key=True, key="_upd-portfolio_")]])],
         [sg.Column([[sg.Table(values=values,
                        headings=data_n_headers[1],
                        display_row_numbers=True,
                        auto_size_columns=True,
                        header_font=font_header,
                        text_color='white',
                        font=font_body,
                        justification='left',
                        alternating_row_color='grey',
                        # num_rows=30, #len(data_n_headers[0]),
                        enable_events=True,
                        key='_portfolio_'), sg.Stretch()]])]
         ]
    return layout


def layout_traders(data_n_headers, font_body, font_header):
    
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [[
        sg.Column([
            [
            sg.Text('Include:  Authors: ', auto_size_text=True,tooltip=tip), sg.Listbox(_analyst_list, default_values=['All'], select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, key=f'track_filt_author',tooltip=tip, size=(20,3)),
            sg.Text('Date from: ', tooltip=tlp_date), sg.Combo(['today', 'week', 'month'], default_value='week',
                                                               key=f'track_filt_date_frm', tooltip=tlp_date),
            sg.Text(' To: ', tooltip=tlp_date), sg.Combo(['today', 'week', 'month'], default_value='',
                                                         key=f'track_filt_date_to', tooltip=tlp_date),
            sg.Text(' Symbols: ',tooltip=tip), sg.Input(key=f'track_filt_sym',tooltip=tip),
            sg.Text(' Channels: ',tooltip=tip), sg.Input(key=f'track_filt_chn',tooltip=tip),
            sg.Text(' DTE: min', tooltip="Days To Expiration min"), 
            sg.Input(key=f'track_dte_min', tooltip="Days To Expiration min"),
            sg.Text(' max', tooltip="Days To Expiration max"), 
            sg.Input(key=f'track_dte_max', tooltip="Days To Expiration max"),
            ],[ 
            sg.Text("Exclude: |"),
            sg.Checkbox("Closed", key="-track-Closed", enable_events=True),
            sg.Checkbox("Open", key="-track-Open", enable_events=True),
            sg.Checkbox("Neg PnL", key="-track-NegPnL", enable_events=True),
            sg.Checkbox("Pos PnL", key="-track-PosPnL", enable_events=True),
            sg.Checkbox("Live PnL", key="-track-live PnL", enable_events=True), 
            sg.Checkbox("Stocks", key="-track-stocks", default=True, enable_events=True),
            sg.Checkbox("Options", key="-track-options", enable_events=True),
            sg.Checkbox("BTO", key="-track-bto", enable_events=True),
            sg.Checkbox("STO", key="-track-sto", enable_events=True),
            sg.Text('| Excl Authors: ', auto_size_text=True,tooltip=tip), sg.Listbox(_analyst_list, default_values=[], select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, key=f'track_exc_author', tooltip=tip, size=(20,3)),
            sg.Text('Symbols: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'track_exc_sym',tooltip=tip),
            sg.Text('Channels: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'track_exc_chn',tooltip=tip),
            ],[sg.ReadButton("Update", button_color=('white', 'black'),bind_return_key=True, key="_upd-track_")]
            ])],
         [sg.Column([
            [
            sg.Table(values=values,
                headings=data_n_headers[1],
                display_row_numbers=True,
                auto_size_columns=True,
                header_font=font_header,
                text_color='white',
                font=font_body,
                justification='left',
                alternating_row_color='grey',
                enable_events=True,
                # num_rows=30, #len(data_n_headers[0]),
                key='_track_'), sg.Stretch()]])]
         ]
    return layout


def layout_stats(data_n_headers, font_body, font_header):
    
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [
        [sg.Column([[sg.Text('Include:  Authors: ', auto_size_text=True, tooltip=tip), sg.Listbox(_analyst_list, default_values=['All'], select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, key=f'stat_filt_author', tooltip=tip, size=(20,3)),
                     sg.Text('Date from:', tooltip=tlp_date), 
                     sg.Input(key=f'stat_filt_date_frm', default_text='week', tooltip=tlp_date),
                     sg.Text(' To:', size=(5, 1), tooltip=tlp_date), 
                     sg.Input(key=f'stat_filt_date_to', tooltip=tlp_date),
                     sg.Text(' Symbols:'), sg.Input(key=f'stat_filt_sym', tooltip=tip),
                     sg.Text(' Max $:', tooltip="calculate stats limiting trades to max $"), 
                     sg.Input(key=f'stat_max_trade_val', tooltip="calculate stats limiting trades to max $ amount"),
                     sg.Text(' Max quantity:', tooltip="calculate stats limiting trades to max quantity"), 
                     sg.Input(key=f'stat_max_qty', tooltip="calculate stats limiting trades to max quantity"),
                     sg.Text(' DTE: min', tooltip="Days To Expiration min"), 
                     sg.Input(key=f'stat_dte_min', tooltip="Days To Expiration min"),
                     sg.Text(' max', tooltip="Days To Expiration max"), 
                     sg.Input(key=f'stat_dte_max', tooltip="Days To Expiration max"),
                     
                     ],
                     [sg.Text("Exclude: "),
                      sg.Checkbox("Neg PnL", key="-stat-NegPnL", enable_events=True),
                      sg.Checkbox("Pos PnL", key="-stat-PosPnL", enable_events=True),                  
                      sg.Checkbox("Stocks", key="-stat-stocks", default=True, enable_events=True),
                      sg.Checkbox("Options", key="-stat-options", enable_events=True),
                      sg.Checkbox("BTO", key="-stat-bto", enable_events=True),
                      sg.Checkbox("STO", key="-stat-sto", enable_events=True),
                      sg.Text('| Excl Authors: ', auto_size_text=True,tooltip=tip), sg.Listbox(_analyst_list, default_values=[], select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, key=f'stat_exc_author', tooltip=tip, size=(20,3)),
                      sg.Text('Symbols: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'stat_exc_sym',tooltip=tip),
                      sg.Text('Channels: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'stat_exc_chn',tooltip=tip),
                      ],
                     [sg.ReadButton("Update", button_color=('white', 'black'),bind_return_key=True, key="_upd-stat_")],
                     [sg.Text("PnL-actual = PnL from prices at the moment of alerted trade (as opposed to the prices claimed in the alert) \n" + \
                         "diff = difference between actual and alerted, high BTO and low STC diffs is bad, alerts are delayed"
                         )]])
                    ],
         [sg.Column([[sg.Table(values=values,
                        headings=data_n_headers[1],
                        display_row_numbers=True,
                        auto_size_columns=True,
                        header_font=font_header,
                        text_color='white',
                        font=font_body,
                        justification='left',
                        alternating_row_color='grey',
                        # num_rows=30, #len(data_n_headers[0]),
                        key='_stat_'), sg.Stretch()]])]
         ]
    return layout

def layout_chan_msg(chn_list, data_n_headers, font_body, font_header):    
    # Handle empy chan history
    if data_n_headers[0] == []: 
        values = [[""*len(data_n_headers[1])] ]
    else:
        values=data_n_headers[0]

    layout = [
        [sg.Text('Analyst Channel: '), sg.Combo(chn_list, default_value=chn_list[0] if chn_list else "", key='_msg_hist_chn_', enable_events=True, size=(20,1)),
         sg.Text(' Authors: '), sg.Input(key='_msg_hist_filt_author_'),
         sg.Text('Date from: ', tooltip=tlp_date), 
         sg.Input(key='_msg_hist_filt_date_frm_', default_text='today', tooltip=tlp_date),
         sg.Text(' To: ', tooltip=tlp_date), sg.Input(key='_msg_hist_filt_date_to_', tooltip=tlp_date),
         sg.Text('Msg contains: '), sg.Input(key='_msg_hist_filt_cont_'),
         ],
        [sg.ReadFormButton("Update", button_color=('white', 'black'), key='_msg_hist_UPD_', bind_return_key=True)],
        [sg.Column([[sg.Table(values=values,
                  headings=data_n_headers[1],
                  justification='left',
                  display_row_numbers=False,
                  text_color='white',
                  font=font_body,
                  header_font=font_header,
                  auto_size_columns =True, max_col_width=30,
                  alternating_row_color='grey',
                  key="_msg_hist_table_")]])]
        ]
    return layout


def tt_acnt(text, fsize=12, bold=True, underline=True, font_name="Arial", size=None, k=None):
    font = [font_name, fsize]
    if bold: font += ['bold']
    if underline: font += ["underline"]
    if size is None:
        size = (len(text) *2, 1)
    if k is not None:
        return sg.T(text,font=font,size=size, key=k)
    else:
        return sg.T(text,font=font,size=size)


def layout_account(bksession, font_body, font_header):
    if bksession is None:
        return [[sg.T("No brokerage API provided in config.ini")]]
    acc_inf, ainf = gg.get_acc_bals(bksession)
    pos_tab, pos_headings = gg.get_pos(acc_inf)
    if not len(pos_tab):
        pos_tab = ["No post"]
    ord_tab, ord_headings, _= gg.get_orders(acc_inf)

    layout = [[sg.Column([
        [tt_acnt("Account ID:", font_body[1]), tt_acnt(ainf["id"], font_body[1], 0, 0, font_body[0]),
         tt_acnt("Balance:", font_body[1]), tt_acnt("$" + str(ainf["balance"]), font_body[1], 0, 0, font_body[0], k="acc_b"),
         tt_acnt("Cash:", font_body[1]), tt_acnt("$" + str(ainf["cash"]), font_body[1], 0, 0, font_body[0], k="acc_c"),
         tt_acnt("Funds:", font_body[1]), tt_acnt("$" + str(ainf["funds"]), font_body[1], 0, 0, font_body[0], k="acc_f")
         ],[sg.ReadFormButton("Update", button_color=('white', 'black'), key='acc_updt', bind_return_key=True)]
             ])],
        [sg.Column(
            [
             [sg.T("Positions", font=(font_body[0], font_body[1], 'bold', "underline"),size=(20,1.5))],
             [sg.Table(values=pos_tab, headings=pos_headings,justification='left',
              display_row_numbers=False, text_color='white', font=font_body,
               auto_size_columns=True,
               header_font=font_header,
              alternating_row_color='grey',
               max_col_width=30,
              key='_positions_')]]),
        sg.Column(
            [
             [sg.T("Orders",font=(font_header[0], font_header[1], 'bold', "underline"),size=(20,1.5))],
             [sg.Table(values=ord_tab, headings=ord_headings,justification='left',
              display_row_numbers=False, text_color='white', font=font_body,
              auto_size_columns=True, 
              header_font=font_header,
              key='_orders_')]])
            ]]
    return layout


def update_acct_ly(bksession, window):

    acc_inf, ainf = gg.get_acc_bals(bksession)
    pos_tab, _ = gg.get_pos(acc_inf)
    ord_tab, _, _= gg.get_orders(acc_inf)

    window.Element("acc_b").update(ainf["balance"])
    window.Element("acc_c").update(ainf["cash"])
    window.Element("acc_f").update(ainf["funds"])

    window.Element("_positions_").update(pos_tab)
    window.Element("_orders_").update(ord_tab)
    
    for el in ["_positions_", "_orders_"]:
        window.Element(el).Widget.resizeRowsToContents()
        window.Element(el).Widget.resizeColumnsToContents()


def get_all_available_authors(cfg):
    authors = []
    for chn in channel_ids.keys():
        csv_path = os.path.join(cfg['general']['data_dir'], f"{chn}_message_history.csv")
        if os.path.exists(csv_path):
            try:
                at = pd.read_csv(csv_path)["Author"].dropna().unique()
                authors.extend(at)
            except Exception:
                pass
    
    subs = [a.strip() for a in cfg['discord']['authors_subscribed'].split(',') if a.strip()]
    authors.extend(subs)
    
    # Case-insensitive deduplication (keeping the first case version we find)
    seen = set()
    unique_authors = []
    for a in authors:
        a_clean = a.strip()
        if not a_clean:
            continue
        a_lower = a_clean.lower()
        if a_lower not in seen:
            seen.add(a_lower)
            unique_authors.append(a_clean)
            
    unique_authors.sort(key=str.lower)
    return unique_authors


def layout_config(fnt_h, cfg):
    frame_gen = [[sg.Checkbox("Notify alerts to discord", default=cfg['discord'].getboolean('notify_alerts_to_discord'),
                        key="cfg_discord.notify_alerts_to_discord", text_color='white', enable_events=True,
                        tooltip='Option to send an your trade alerts to a channel using webhook specified in config.ini')],
            [sg.Text("off market hours:"), 
                sg.Input(cfg['general']['off_hours'],key="cfg_general.off_hours", 
                    tooltip='set your local hours where market is closed, e.g. 16,9 means from 4pm to 9am [eastern time]')],
            ]
        
    all_authors = get_all_available_authors(cfg)
    subscribed = [a.strip() for a in cfg['discord']['authors_subscribed'].split(',') if a.strip()]
    subscribed = [s for s in subscribed if s in all_authors]

    frame_long = [
        [sg.Checkbox('Do BTO trades', cfg['general'].getboolean('Do_BTO_trades'), text_color='white',
                    key="cfg_general.do_BTO_trades", tooltip='Accept Buy alerts and open trades', enable_events=True)],
        [sg.Checkbox('Do STC trades', cfg['general'].getboolean('Do_STC_trades'), text_color='white',
                    key="cfg_general.do_STC_trades", tooltip='Accept Sell alerts and close trade', enable_events=True)],
        [sg.Checkbox('Move Stop to Break-Even after PT1 is hit', cfg['risk_management'].getboolean('move_to_breakeven_pt1', False), text_color='white',
                    key="cfg_risk_management.move_to_breakeven_pt1", tooltip='Automatically move stop loss to entry price when PT1 is reached', enable_events=True)],
        [sg.Text("Authors subscribed (select from list to auto-fill below):", tooltip='List of authors to follow')], 
        [sg.Listbox(all_authors, default_values=subscribed, select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE, 
                    key="cfg_discord.authors_subscribed_list", size=(30, 6), enable_events=True)],
        [sg.Input(cfg['discord']['authors_subscribed'],key="cfg_discord.authors_subscribed", enable_events=True)],
        [sg.Text("Trade capital: $"), sg.Input(cfg['order_configs']['trade_capital'], key="cfg_order_configs.trade_capital", size=(15,1), enable_events=True),
         sg.Text("Max capital: $"), sg.Input(cfg['order_configs']['max_trade_capital'], key="cfg_order_configs.max_trade_capital", size=(15,1), enable_events=True)],
        ]
    
    frame_short = [
        [sg.Checkbox('Do STO trades', cfg['shorting'].getboolean('DO_STO_TRADES'), text_color='white',enable_events=True,
                    key="cfg_shorting.DO_STO_TRADES")],
        [sg.Checkbox("Do BTC trades", cfg['shorting'].getboolean('DO_BTC_TRADES'), 
                     enable_events=True, key="cfg_shorting.DO_BTC_TRADES",text_color='white')], 
        [sg.Text("STO price:"), sg.Drop(values=['bid', 'ask', 'mid', 'last', 'alert'], default_value=cfg['shorting']['STO_price'],
                key="cfg_shorting.STO_price",enable_events=True, size=(10,1))],
        [sg.Text("PT %:"), sg.Input(cfg['shorting']['BTC_PT'], key="cfg_shorting.BTC_PT", size=(10,1), enable_events=True),
         sg.Text("SL %:"), sg.Input(cfg['shorting']['BTC_SL'], key="cfg_shorting.BTC_SL", size=(10,1), enable_events=True)],
        [sg.Text("Margin capital: $"), sg.Input(cfg['shorting']['margin_capital'], key="cfg_shorting.margin_capital", size=(15,1), enable_events=True)],
    ]

    # Pre-parse default exits JSON string
    try:
        exits_dict = eval(cfg['order_configs'].get('default_exits', '{"PT1": None, "PT2": None, "PT3": None, "SL": None}'))
    except Exception:
        exits_dict = {"PT1": None, "PT2": None, "PT3": None, "SL": None}
        
    pt1_val = exits_dict.get("PT1") or ""
    pt2_val = exits_dict.get("PT2") or ""
    pt3_val = exits_dict.get("PT3") or ""
    sl_val = exits_dict.get("SL") or ""

    frame_exits = [
        [sg.Text("PT1 % (e.g., 30% or 30%TS5%):", size=(25, 1)), sg.Input(pt1_val, key="cfg_exits_PT1", size=(15, 1))],
        [sg.Text("PT2 %:", size=(25, 1)), sg.Input(pt2_val, key="cfg_exits_PT2", size=(15, 1))],
        [sg.Text("PT3 %:", size=(25, 1)), sg.Input(pt3_val, key="cfg_exits_PT3", size=(15, 1))],
        [sg.Text("Stop Loss (SL) % (e.g., 15%):", size=(25, 1)), sg.Input(sl_val, key="cfg_exits_SL", size=(15, 1))]
    ]

    active_strat = cfg['order_configs'].get('active_exit_strategy', 'Original STC')
    mae_mult = cfg['order_configs'].get('mae_multiplier', '1.5')
    ts_pct = cfg['order_configs'].get('fixed_ts_pct', '10.0')
    atr_mult = cfg['order_configs'].get('atr_multiplier', '2.0')

    frame_strat = [
        [sg.Text("Active Exit Strategy:", size=(25, 1)), 
         sg.Drop(values=["Original STC", "Manual Default Exits", "Strategy 1 (Trim Detector)", "Strategy 2 (MAE Stop)", "Strategy 3 (Fixed Trailing Stop)", "Strategy 4 (ATR TS)"], 
                 default_value=active_strat, key="cfg_order_configs.active_exit_strategy", size=(30, 1), enable_events=True)],
        [sg.Text("Strategy 2 MAE Multiplier:", size=(25, 1)), sg.Input(mae_mult, key="cfg_order_configs.mae_multiplier", size=(15, 1))],
        [sg.Text("Strategy 3 Trailing Stop %:", size=(25, 1)), sg.Input(ts_pct, key="cfg_order_configs.fixed_ts_pct", size=(15, 1))],
        [sg.Text("Strategy 4 ATR Multiplier:", size=(25, 1)), sg.Input(atr_mult, key="cfg_order_configs.atr_multiplier", size=(15, 1))]
    ]

    lay = [
        [sg.Text("Session Configuration", font=("Helvetica", 16, "bold"), pad=(0, 10))],
        [
            sg.Column([
                [sg.Frame('General Settings', frame_gen, title_color='#00ff00', pad=(5, 5))],
                [sg.Frame('Long Position Config', frame_long, title_color='#00ff00', pad=(5, 5))],
                [sg.Frame('Short Position Config', frame_short, title_color='#ff0000', pad=(5, 5))]
            ]),
            sg.Column([
                [sg.Frame('Default Exits Configuration', frame_exits, title_color='#00ff00', pad=(5, 5))],
                [sg.Frame('Exit Strategy Menu', frame_strat, title_color='#00ff00', pad=(5, 5))]
            ])
        ],
        [sg.ReadButton("SAVE CHANGES", button_color=('white', '#1a73e8'), key="cfg_button", size=(20, 1), pad=(0, 10))]
    ]
    
    return lay


def layout_strategy_exits(comp_data_headers, opt_data_headers, font_body, font_header):
    comp_values, comp_headings = comp_data_headers
    opt_values, opt_headings = opt_data_headers
    
    if not comp_values:
        comp_values = [[""] * 7]
        comp_headings = ["Strategy", "Total Trades", "Win Rate %", "Total Profit $", "Avg Return %", "Profit Factor", "Max Drawdown $"]
        
    if not opt_values:
        opt_values = [[""] * 9]
        opt_headings = ["Trader", "Total Trades", "Original Profit $", "Original Win Rate %", "Optimal Strategy", "Optimal Parameter", "Optimal Profit $", "Optimal Win Rate %", "Profit Factor"]

    layout = [
        [sg.Text("Backtested Exit Strategy Analysis", font=("Helvetica", 16, "bold"), pad=(0, 10))],
        [sg.Text("Compare the performance of different virtual exit strategies simulated on historical trade alerts.", font=font_body)],
        [sg.Frame("Overall Exit Strategy Performance", [
            [sg.Table(values=comp_values,
                      headings=comp_headings,
                      justification='left',
                      display_row_numbers=False,
                      text_color='white',
                      font=font_body,
                      header_font=font_header,
                      auto_size_columns=True,
                      alternating_row_color='grey',
                      key="_strat_comp_table_")]
        ], title_color='#00ff00', pad=(5, 10))],
        [sg.Frame("Trader-Specific Exit Optimizations", [
            [sg.Table(values=opt_values,
                      headings=opt_headings,
                      justification='left',
                      display_row_numbers=False,
                      text_color='white',
                      font=font_body,
                      header_font=font_header,
                      auto_size_columns=True,
                      alternating_row_color='grey',
                      key="_trader_opt_table_")]
        ], title_color='#00ff00', pad=(5, 10))],
        [sg.ReadButton("Refresh Analysis Data", button_color=('white', '#1a73e8'), key="_refresh_strat_exits_", size=(25, 1), pad=(0, 10))]
    ]
    return layout





