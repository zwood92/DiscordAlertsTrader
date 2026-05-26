
import os
import time
import pandas as pd
from datetime import datetime, timezone, date, timedelta
import threading
from colorama import Fore, init
import discord # this is discord.py-self package not discord
import sys

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Set default encoding to utf-8 for stdout to handle emojis in Discord messages
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from DiscordAlertsTrader.message_parser import parse_trade_alert
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.configurator import channel_ids
from DiscordAlertsTrader.alerts_trader import AlertsTrader, find_last_trade
from DiscordAlertsTrader.alerts_tracker import AlertsTracker
from DiscordAlertsTrader.strategy_analyzer import detect_exit_signal
from DiscordAlertsTrader.server_alert_formatting import server_formatting
try:
    from custom_msg_format import msg_custom_formated, msg_custom_formated2
    print("custom message format loaded")
    custom = True
except ImportError:
    custom = False


init(autoreset=True)

class dummy_queue():
    def __init__(self, maxsize=10):
        self.maxsize = maxsize
        self.queue = []

    def put(self, item):
        if len(self.queue) >= self.maxsize:
            self.queue.pop(0)
        self.queue.append(item)

def split_strip(string):
    lstr = string.split(",")
    lstr = [s.strip().lower() for s in lstr]
    return lstr

class DiscordBot(discord.Client):
    def __init__(self, 
                 queue_prints=dummy_queue(maxsize=10), 
                 live_quotes=True, 
                 brokerage=None,
                 tracker_portfolio_fname=cfg['portfolio_names']["tracker_portfolio_name"],
                 cfg = cfg):
        super().__init__()
        self.channel_IDS = channel_ids
        self.time_strf = "%Y-%m-%d %H:%M:%S.%f"
        self.queue_prints = queue_prints
        self.bksession = brokerage
        self.live_quotes = live_quotes
        self.cfg = cfg
        if brokerage is not None:
            self.trader = AlertsTrader(queue_prints=self.queue_prints, brokerage=brokerage, cfg=self.cfg)       
        self.tracker = AlertsTracker(brokerage=brokerage, portfolio_fname=tracker_portfolio_fname, cfg=self.cfg)
        
        # Initialize virtual strategy trackers
        data_dir = os.path.dirname(tracker_portfolio_fname) if os.path.dirname(tracker_portfolio_fname) else "data"
        self.tracker_trim = AlertsTracker(brokerage=brokerage, portfolio_fname=os.path.join(data_dir, "strat_trim_portfolio.csv"), cfg=self.cfg)
        self.tracker_mae = AlertsTracker(brokerage=brokerage, portfolio_fname=os.path.join(data_dir, "strat_mae_stop_portfolio.csv"), cfg=self.cfg)
        self.tracker_fixed_ts = AlertsTracker(brokerage=brokerage, portfolio_fname=os.path.join(data_dir, "strat_fixed_ts_portfolio.csv"), cfg=self.cfg)
        self.tracker_atr_ts = AlertsTracker(brokerage=brokerage, portfolio_fname=os.path.join(data_dir, "strat_atr_ts_portfolio.csv"), cfg=self.cfg)
        
        self.load_data()        

        if TTS_AVAILABLE and cfg['risk_management'].getboolean('enable_tts'):
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)
            except Exception as e:
                print(f"Failed to initialize TTS: {e}")
                self.tts_engine = None
        else:
            self.tts_engine = None

        if (live_quotes and brokerage is not None and brokerage.name != 'webull') \
            or (brokerage is not None and brokerage.name == 'webull' and 
                cfg['general'].getboolean('webull_live_quotes')):
            self.thread_liveq =  threading.Thread(target=self.track_live_quotes)
            self.thread_liveq.start()

    def close_bot(self):
        if self.bksession is not None:
            self.trader.update_portfolio = False
            self.live_quotes = False

    def track_live_quotes(self):
        dir_quotes = self.cfg['general']['data_dir'] + '/live_quotes'
        os.makedirs(dir_quotes, exist_ok=True)

        while self.live_quotes:
            # Skip closed market
            now = datetime.now()
            weekday, hour = now.weekday(), now.hour
            after_hr, before_hr = self.cfg['general']['off_hours'].split(",")
            if  weekday >= 5 or (hour < int(before_hr) or hour >= int(after_hr)):  
                time.sleep(60)
                continue

            # get unique symbols  from portfolios, either options or all, open or alerted today
            tk_day = pd.to_datetime(self.tracker.portfolio['Date']).dt.date == date.today()
            td_day = pd.to_datetime(self.trader.portfolio['Date']).dt.date == date.today()
            msk_tk = ((self.tracker.portfolio['isOpen']==1) | tk_day) 
            msk_td = ((self.trader.portfolio['isOpen']==1) | td_day) 
            
            if self.cfg['general'].getboolean('live_quotes_options_only'):
                msk_tk = msk_tk & (self.tracker.portfolio['Asset']=='option')
                msk_td = msk_td & (self.trader.portfolio['Asset']=='option')
            
            track_symb = set(self.tracker.portfolio.loc[msk_tk, 'Symbol'].to_list() + \
                self.trader.portfolio.loc[msk_td, 'Symbol'].to_list())
            if not len(track_symb):
                time.sleep(5)
                continue
            # save quotes to file
            try:
                quote = self.bksession.get_quotes(track_symb)
            except Exception as e:
                print('error during live quote:', e)
                continue
            if quote is None:
                continue
            
            for q in quote: 
                if quote[q].get('description') == 'Symbol not found' or q =='' or quote[q]['bidPrice'] == 0:
                    continue
                timestamp = quote[q]['quoteTimeInLong']//1000  # in ms

                # Read the last line of the file and get the last recorded timestamp for the symbol
                file_path = f"{dir_quotes}/{quote[q]['symbol']}.csv"
                last_line = ""
                do_header = True
                if os.path.exists(file_path):
                    do_header = False
                    with open(file_path, "r") as f:
                        lines = f.readlines()
                        if lines:
                            last_line = lines[-1].strip()
                
                #if last recorded timestamp is the same as current, skip
                if len(last_line) and float(last_line.split(",")[1] )== quote[q]['bidPrice'] and float(last_line.split(",")[2] )== quote[q]['askPrice']:
                    continue
                
                # Write the new line to the file
                with open(file_path, "a+") as f:
                    if do_header:
                        f.write(f"timestamp, quote, quote_ask\n")
                    f.write(f"{timestamp}, {quote[q]['bidPrice']}, {quote[q]['askPrice']}\n")
                
                # Update virtual exits based on live quotes
                self.check_virtual_exits(q, quote[q])
            
            # Sleep for up to X secs    
            toc = (datetime.now() - now).total_seconds()
            if toc < float(cfg['general']['sampling_rate_quotes']) and self.live_quotes:
                time.sleep(float(cfg['general']['sampling_rate_quotes'])-toc)

    def check_virtual_exits(self, symbol, quote_data):
        bid = quote_data.get('bidPrice', quote_data.get('lastPrice', 0))
        ask = quote_data.get('askPrice', quote_data.get('lastPrice', 0))
        if bid == 0 or ask == 0:
            return
            
        # 1. Tracker MAE Check
        open_mae = self.tracker_mae.portfolio[
            (self.tracker_mae.portfolio['Symbol'] == symbol) & 
            (self.tracker_mae.portfolio['isOpen'] == 1)
        ]
        for idx, row in open_mae.iterrows():
            entry = float(row['Price'])
            sl = float(row.get('SL', 20.0))
            pt = float(row.get('PT', 40.0))
            sl_price = entry * (1.0 - sl / 100)
            pt_price = entry * (1.0 + pt / 100)
            
            triggered = False
            exit_price = None
            if bid <= sl_price:
                triggered = True
                exit_price = sl_price
            elif ask >= pt_price:
                triggered = True
                exit_price = pt_price
                
            if triggered:
                virtual_stc = {
                    "action": "STC",
                    "Symbol": symbol,
                    "Trader": row['Trader'],
                    "Qty": row['Qty'],
                    "price": exit_price,
                    "Date": datetime.now().strftime(self.time_strf)
                }
                self.tracker_mae.trade_alert(virtual_stc, live_alert=False)
                
        # 2. Tracker Fixed TS Check
        open_fixed = self.tracker_fixed_ts.portfolio[
            (self.tracker_fixed_ts.portfolio['Symbol'] == symbol) & 
            (self.tracker_fixed_ts.portfolio['isOpen'] == 1)
        ]
        for idx, row in open_fixed.iterrows():
            entry = float(row['Price'])
            ts_pct = float(row.get('SL', 30.0))
            peak = float(row.get('peak', entry))
            if ask > peak:
                peak = ask
                self.tracker_fixed_ts.portfolio.loc[idx, 'peak'] = peak
                self.tracker_fixed_ts.portfolio.to_csv(self.tracker_fixed_ts.portfolio_fname, index=False)
                
            stop_level = peak * (1.0 - ts_pct / 100)
            if bid <= stop_level:
                virtual_stc = {
                    "action": "STC",
                    "Symbol": symbol,
                    "Trader": row['Trader'],
                    "Qty": row['Qty'],
                    "price": stop_level,
                    "Date": datetime.now().strftime(self.time_strf)
                }
                self.tracker_fixed_ts.trade_alert(virtual_stc, live_alert=False)
                
        # 3. Tracker ATR TS Check
        open_atr = self.tracker_atr_ts.portfolio[
            (self.tracker_atr_ts.portfolio['Symbol'] == symbol) & 
            (self.tracker_atr_ts.portfolio['isOpen'] == 1)
        ]
        for idx, row in open_atr.iterrows():
            entry = float(row['Price'])
            ts_pct = float(row.get('SL', 20.0))
            peak = float(row.get('peak', entry))
            if ask > peak:
                peak = ask
                self.tracker_atr_ts.portfolio.loc[idx, 'peak'] = peak
                self.tracker_atr_ts.portfolio.to_csv(self.tracker_atr_ts.portfolio_fname, index=False)
                
            stop_level = peak * (1.0 - ts_pct / 100)
            if bid <= stop_level:
                virtual_stc = {
                    "action": "STC",
                    "Symbol": symbol,
                    "Trader": row['Trader'],
                    "Qty": row['Qty'],
                    "price": stop_level,
                    "Date": datetime.now().strftime(self.time_strf)
                }
                self.tracker_atr_ts.trade_alert(virtual_stc, live_alert=False)

    def load_data(self):
        self.chn_hist= {}
        self.chn_hist_fname = {}
        for ch in self.channel_IDS.keys():
            dt_fname = f"{self.cfg['general']['data_dir']}/{ch}_message_history.csv"
            if not os.path.exists(dt_fname):
                ch_dt = pd.DataFrame(columns=self.cfg['col_names']['chan_hist'].split(","))
                ch_dt.to_csv(dt_fname, index=False)
                ch_dt.to_csv(f"{self.cfg['general']['data_dir']}/{ch}_message_history_temp.csv", index=False)
            else:
                ch_dt = pd.read_csv(dt_fname)

            self.chn_hist_fname[ch] = dt_fname
            self.chn_hist[ch]= ch_dt

    async def on_ready(self):
        try:
            print('Logged on as', self.user, '\n loading previous messages')
        except UnicodeEncodeError:
            print('Logged on as User ID:', self.user.id, '\n loading previous messages')
        await self.load_previous_msgs()
    
    async def on_message(self, message):
        # only respond to channels in config or authorwise subscription
        author = f"{message.author.name}#{message.author.discriminator}".replace("#0", "")
        
        if message.channel.id == int(cfg['discord']['commands_channel']):
            if message.content.startswith('!close long'):
                cfg['general']['DO_BTO_TRADES'] = 'false'
                print("BTC trades closed")
            elif message.content.startswith('!close short'):
                cfg['shorting']['DO_STO_TRADES'] = 'false'
                print("STO trades closed")
            elif message.content.startswith('!open long'):
                cfg['general']['DO_BTO_TRADES'] = 'true'
                print("BTC trades opened")
            elif message.content.startswith('!open short'):
                cfg['shorting']['DO_STO_TRADES'] = 'true'
                print("STO trades opened")
            return
        elif message.channel.id not in self.channel_IDS.values() and \
            author.lower() not in split_strip(self.cfg['discord']['authorwise_subscription']):
            return
        if message.content == 'ping':
            await message.channel.send('pong')
         
        
        message = server_formatting(message)
        if custom:
            await msg_custom_formated2(message)
            alert = msg_custom_formated(message, self.bksession)
            if alert is not None:
                for msg in alert:
                    self.new_msg_acts(msg, False)
                return
        
        if not len(message.content):
            return
        self.new_msg_acts(message)

    # async def on_message_edit(self, before, after):
    #     # Ignore if the message is not from a user or if the bot itself edited the message
    #     if after.channel.id not in self.channel_IDS.values() or  before.author.bot:
    #         return

    #     str_prt = f"Message edited by {before.author}: '{before.content}' -> '{after.content}'"
    #     self.queue_prints.put([str_prt, "black"])
    #     print(Fore.BLUE + str_prt)

    async def load_previous_msgs(self):
        await self.wait_until_ready()
        for ch, ch_id in self.channel_IDS.items():
            channel = self.get_channel(ch_id)
            print(f"Checking access for channel: {ch} (ID: {ch_id})")
            if channel is None:
                print("channel not found or no access:", ch)
                continue
            
            if len(self.chn_hist[ch]):
                msg_last = self.chn_hist[ch].iloc[-1]
                date_After = datetime.strptime(msg_last.Date, self.time_strf) 
                iterator = channel.history(after=date_After, oldest_first=True)
            else:
                date_After = datetime.now() - timedelta(days=90)
                iterator = channel.history(after=date_After, oldest_first=True)
                
            try:
                print("In", channel)
            except UnicodeEncodeError:
                print("In channel ID:", channel.id)
            try:
                async for message in iterator:
                    message = server_formatting(message)
                    if message is None:
                        continue
                    if custom:
                        alert = msg_custom_formated(message)
                        if alert is not None:
                            for msg in alert:
                                self.new_msg_acts(msg, False)
                    else:
                        self.new_msg_acts(message)
            except discord.errors.Forbidden:
                print(f"No permission to read history in {ch}")
        print("Done")        

    def announce_alert(self, author, content):
        if self.tts_engine:
            text = f"New alert from {author}: {content}"
            # Run TTS in a thread to avoid blocking discord bot
            threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    def _speak(self, text):
        try:
            # Need to initialize in each thread for some TTS engines
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"TTS Error: {e}")
        self.tracker.close_expired()
        self.tracker_trim.close_expired()
        self.tracker_mae.close_expired()
        self.tracker_fixed_ts.close_expired()
        self.tracker_atr_ts.close_expired()

    def new_msg_acts(self, message, from_disc=True):
        if not hasattr(self, 'recent_msgs'):
            self.recent_msgs = []

        if from_disc:
            # Deduplicate messages within 60 seconds
            msg_hash = hash((message.author.name, message.content))
            current_time = time.time()
            self.recent_msgs = [m for m in self.recent_msgs if current_time - m[1] < 60]
            if msg_hash in [m[0] for m in self.recent_msgs]:
                print(f"Skipping duplicate message from {message.author.name}")
                return
            self.recent_msgs.append((msg_hash, current_time))
            
            msg_date = message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None)
            msg_date_f = msg_date.strftime(self.time_strf)    
            if message.channel.id in self.channel_IDS.values():
                chn_ix = list(self.channel_IDS.values()).index(message.channel.id)
                chn = list(self.channel_IDS.keys())[chn_ix]
            else:
                chn = None
            msg = pd.Series({'AuthorID': message.author.id,
                            'Author': f"{message.author.name}#{message.author.discriminator}".replace("#0", ""),
                            'Date': msg_date_f, 
                            'Content': message.content,
                            'Channel': chn
                            })
        else:
            msg = message
        chn = msg['Channel']
        shrt_date = datetime.strptime(msg["Date"], self.time_strf).strftime('%Y-%m-%d %H:%M:%S')
        try:
            self.queue_prints.put([f"\n{shrt_date} {msg['Channel']}: \n\t{msg['Author']}: {msg['Content']} ", "blue"])
            print(Fore.BLUE + f"{shrt_date} \t {msg['Author']}: {msg['Content']} ")
        except UnicodeEncodeError:
            print(Fore.BLUE + f"{shrt_date} \t {msg['Author']}: [Message with special characters]")

        # Check Strategy 1 (Trim/Screenshot Detector) live signals
        if chn != "GUI_user":
            trader = msg['Author']
            open_trades = self.tracker_trim.portfolio[
                (self.tracker_trim.portfolio['Trader'].str.lower() == trader.lower()) &
                (self.tracker_trim.portfolio['isOpen'] == 1)
            ]
            if not open_trades.empty:
                has_attachments = from_disc and len(getattr(message, 'attachments', [])) > 0
                is_exit, qty_pct, msg_price, is_stop = detect_exit_signal(msg['Content'], has_attachments)
                if is_exit:
                    for idx, row in open_trades.iterrows():
                        virtual_stc = {
                            "action": "STC",
                            "Symbol": row['Symbol'],
                            "Trader": row['Trader'],
                            "Qty": row['Qty'] * qty_pct,
                            "price": msg_price if msg_price is not None else self.tracker_trim.price_now(row['Symbol'], "STC"),
                            "Date": msg['Date']
                        }
                        if virtual_stc["price"] is None:
                            virtual_stc["price"] = row['Price']
                        self.tracker_trim.trade_alert(virtual_stc, live_alert=False, channel=chn)

        # Skip messages with no text content (images, embeds, etc.)
        if not msg['Content']:
            return

        pars, order =  parse_trade_alert(msg['Content'])
        if pars is None:
            if self.chn_hist.get(chn) is not None:
                msg['Parsed'] = ""
                self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
            return
        else:
            if 'put_lower_strike' in msg.keys():
                order['asset'] = "option"
                order.update(msg)
            
            if order['asset'] == "option":
                try:
                    # get option date with year
                    if len(order['expDate'].split("/")) ==2:
                        exp_dt = datetime.strptime(f"{order['expDate']}/{datetime.now().year}" , "%m/%d/%Y").date()
                    else:
                        if len(order['expDate'].split("/")[-1]) == 2:
                            exp_dt = datetime.strptime(f"{order['expDate']}" , "%m/%d/%y").date()
                        else:
                            exp_dt = datetime.strptime(f"{order['expDate']}", "%m/%d/%Y").date()
                except ValueError:
                    str_msg = f"Option date is wrong: {order['expDate']}"
                    self.queue_prints.put([f"\t {str_msg}", "green"])
                    print(Fore.GREEN + f"\t {str_msg}")
                    msg['Parsed'] = str_msg
                    if self.chn_hist.get(chn) is not None:
                        self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                        self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
                    return
                    
                dt = datetime.now().date()
                order['dte'] =  (exp_dt - dt).days
                if order['dte']<0:
                    str_msg = f"Option date in the past: {order['expDate']}"
                    self.queue_prints.put([f"\t {str_msg}", "green"])
                    print(Fore.GREEN + f"\t {str_msg}")
                    msg['Parsed'] = str_msg
                    if self.chn_hist.get(chn) is not None:
                        self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                        self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
                    return

            order['Trader'], order["Date"] = msg['Author'], msg["Date"]
            order_date = datetime.strptime(order["Date"], "%Y-%m-%d %H:%M:%S.%f")
            date_diff = abs(datetime.now() - order_date)
            print(f"time difference is {date_diff.total_seconds()}")

            live_alert = True if date_diff.seconds < 90 else False
            str_msg = pars
            if live_alert and self.bksession is not None and (order.get('price') is not None):
                quote = self.trader.price_now(order['Symbol'], order["action"], pflag=1)
                act_diff =-1
                if quote:
                    if quote > 0:
                        order['price_actual'] = quote
                    if order['price'] == 0:
                        str_msg = f"ALerted price is 0, skipping alert "
                        self.queue_prints.put([f"\t {str_msg}", "green"])
                        print(Fore.GREEN + f"\t {str_msg}")
                        return
                    act_diff = max(((quote - order['price'])/order['price']), (order['price'] - quote)/ quote)
                    # Check if actual price is too far (100) from alerted price
                    if abs(act_diff) > 1 and order.get('action') == 'BTO' and 'put_lower_strike' not in msg.keys():
                        str_msg = f"Alerted price is {act_diff} times larger than current price of {quote}, skipping alert"
                        self.queue_prints.put([f"\t {str_msg}", "green"])
                        print(Fore.GREEN + f"\t {str_msg}")
                        msg['Parsed'] = str_msg
                        if self.chn_hist.get(chn) is not None:
                            self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                            self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
                        return
                
                str_msg += f" Actual:{quote}, diff {round(act_diff*100)}%"
            self.queue_prints.put([f"\t {str_msg}", "green"])
            print(Fore.GREEN + f"\t {str_msg}")
            #Tracker
            if chn != "GUI_user":
                track_out = self.tracker.trade_alert(order, live_alert, chn)
                self.queue_prints.put([f"{track_out}", "red"])
                
                # Update virtual portfolios
                self.tracker_trim.trade_alert(order, live_alert, chn)
                self.tracker_mae.trade_alert(order, live_alert, chn)
                self.tracker_fixed_ts.trade_alert(order, live_alert, chn)
                self.tracker_atr_ts.trade_alert(order, live_alert, chn)
                
                if order["action"] in ["BTO", "STO"]:
                    # 1. Setup MAE stop levels
                    open_mae, _ = find_last_trade(order, self.tracker_mae.portfolio, open_only=True)
                    if open_mae is not None:
                        trader = order["Trader"]
                        closed_trades = self.tracker_mae.portfolio[
                            (self.tracker_mae.portfolio['Trader'].str.lower() == trader.lower()) &
                            (self.tracker_mae.portfolio['isOpen'] == 0)
                        ]
                        maes = []
                        for _, c_row in closed_trades.iterrows():
                            from DiscordAlertsTrader.strategy_analyzer import parse_trail_stats
                            mae, _, _, _, _ = parse_trail_stats(c_row.get('TrailStats'))
                            if mae is not None:
                                maes.append(mae)
                        avg_mae = sum(maes)/len(maes) if maes else 20.0
                        sl_pct = avg_mae * 2.5
                        pt_pct = sl_pct * 2.0
                        self.tracker_mae.portfolio.loc[open_mae, "SL"] = sl_pct
                        self.tracker_mae.portfolio.loc[open_mae, "PT"] = pt_pct
                        self.tracker_mae.portfolio.to_csv(self.tracker_mae.portfolio_fname, index=False)
                        
                    # 2. Setup Fixed TS peak/TS %
                    open_fixed, _ = find_last_trade(order, self.tracker_fixed_ts.portfolio, open_only=True)
                    if open_fixed is not None:
                        self.tracker_fixed_ts.portfolio.loc[open_fixed, "SL"] = 30.0
                        self.tracker_fixed_ts.portfolio.loc[open_fixed, "peak"] = float(order["price"])
                        self.tracker_fixed_ts.portfolio.to_csv(self.tracker_fixed_ts.portfolio_fname, index=False)
                        
                    # 3. Setup ATR TS peak/TS %
                    open_atr, _ = find_last_trade(order, self.tracker_atr_ts.portfolio, open_only=True)
                    if open_atr is not None:
                        symbol = order["Symbol"]
                        is_option = "_" in symbol
                        underlying = symbol.split("_")[0] if is_option else symbol
                        atr = None
                        try:
                            import yfinance as yf
                            hist = yf.Ticker(underlying).history(period="1mo", interval="1d")
                            if not hist.empty and len(hist) >= 14:
                                high_low = hist['High'] - hist['Low']
                                high_close = abs(hist['High'] - hist['Close'].shift())
                                low_close = abs(hist['Low'] - hist['Close'].shift())
                                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                                true_range = ranges.max(axis=1)
                                atr = true_range.rolling(14).mean().iloc[-1]
                        except Exception:
                            pass
                        
                        entry_price = float(order["price"])
                        if atr is None:
                            atr = entry_price * 0.05
                        
                        if entry_price <= 0:
                            stop_distance_pct = 20.0
                        elif is_option:
                            atr_option = atr * 0.40
                            stop_distance_pct = (atr_option / entry_price) * 100.0 * 2.0
                        else:
                            stop_distance_pct = (atr / entry_price) * 100.0 * 2.0
                            
                        stop_distance_pct = max(10.0, min(60.0, stop_distance_pct))
                        self.tracker_atr_ts.portfolio.loc[open_atr, "SL"] = stop_distance_pct
                        self.tracker_atr_ts.portfolio.loc[open_atr, "peak"] = entry_price
                        self.tracker_atr_ts.portfolio.to_csv(self.tracker_atr_ts.portfolio_fname, index=False)
            # Trader
            do_trade, order = self.do_trade_alert(msg['Author'], msg['Channel'], order)
            if do_trade and date_diff.seconds < 120:
                self.announce_alert(msg['Author'], msg['Content'])
                order["Trader"] = msg['Author']
                self.trader.new_trade_alert(order, pars, msg['Content'])
        
        if self.chn_hist.get(chn) is not None:
            msg['Parsed'] = pars
            self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
            self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
    
    def do_trade_alert(self, author, channel, order):
        "Decide if alert should be traded"
        if self.bksession is None or channel == "GUI_analysts":
            return False, order
        
        # in authors subs list or channel subs list
        if author.lower() in split_strip(self.cfg['discord']['authors_subscribed']) or \
            channel.lower() in split_strip(self.cfg['discord']['channelwise_subscription']):
            # ignore if no STC
            if not self.cfg['general'].getboolean('DO_STC_TRADES') and order['action'] == "STC" \
            and channel not in ["GUI_user", "GUI_both"]:        
                str_msg = f"STC not accepted by config options: DO_STC_TRADES = False"
                print(Fore.GREEN + str_msg)
                self.queue_prints.put([str_msg, "", "green"])
                return False, order
            else:
                if order['action'] == "BTO" and order['asset'] == 'option':
                    min_price = cfg['order_configs']['min_opt_price']
                    if len(min_price) and order['price'] *100 < float(cfg['order_configs']['min_opt_price']):
                        str_msg = f"Option price is too small as per config: {order['price']}"
                        print(Fore.GREEN + str_msg)
                        self.queue_prints.put([str_msg, "", "green"])
                        return False, order
                return True, order

        # in authors shorting list
        elif author.lower() in split_strip(self.cfg['shorting']['authors_subscribed']):

            # short order sent manullay from gui
            if order["action"] in ["BTC", "STO"] and channel in ["GUI_user", "GUI_both"]:
                return True, order
            # Make it shorting order
            order["action"] = "STO" if order["action"] == "BTO" else "BTC" if order["action"] == "STC" else order["action"]
            # reject if cfg do BTO or STC is false
            if (order["action"] == "BTC" and not self.cfg['shorting'].getboolean('DO_BTC_TRADES')) \
                or (order["action"] == "STO" and not self.cfg['shorting'].getboolean('DO_STO_TRADES')):
                return False, order
            
            if order['asset'] == 'stock':
                return True, order
            
            if len(self.cfg['shorting']['max_dte']):
                if order['dte'] <= int(self.cfg['shorting']['max_dte']):
                    return True, order
                else:
                    str_msg = f"STO {order['dte']} DTE smaller than max in config: {self.cfg['shorting']['max_dte']}, order aborted"
                    print(Fore.RED + str_msg)
                    self.queue_prints.put([str_msg, "", "red"])
                    return False, order
                
        return False, order

if __name__ == '__main__':
    from DiscordAlertsTrader.configurator import cfg, channel_ids, get_discord_token
    from DiscordAlertsTrader.brokerages import get_brokerage
    bksession = get_brokerage()
    client = DiscordBot(brokerage=bksession, cfg=cfg, live_quotes=False)
    client.run(get_discord_token())



