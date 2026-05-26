import schwab
from DiscordAlertsTrader.configurator import cfg

import httpx
import os

from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.brokerages import BaseBroker, retry_on_exception


class SW(BaseBroker):
    def __init__(self, accountId=None):
        """
        accountId: id of the account
        """
        self.name = 'ts'
        self.accountId = accountId

    def get_session(self):       
        if len(cfg['schwab']['key']) < 10:
            raise ValueError( "No Schawb secret key found, fill it in the config.ini file")
        
        if not os.path.exists('schwab_token.json'):
            # Create a new session
            self.session = schwab.auth.client_from_manual_flow(cfg['schwab']['key'],
                                                            cfg['schwab']['secret'],
                                                            cfg['schwab']['redirect_url'], 
                                                            token_path='schwab_token.json')
        else:
            self.session = schwab.auth.client_from_token_file('schwab_token.json',
                                                              cfg['schwab']['key'],
                                                              cfg['schwab']['secret'])
        
        resp = self.session.get_account_numbers()
        assert resp.status_code == httpx.codes.OK
        self.accountId = resp.json()[0]['hashValue']
            
        success = not self.session.session.is_closed
        if success:
            print("Logged in Schwab successfully")
        else:
            print("Failed to login Schwab")
        return success
    

    def _convert_option_fromsw(self, ticker):
        """
        Convert ticker from 'SPX yearmonthdayC00011000' to 'SPX_monthdayyearC110' format.
        
        Parameters:
        ticker (str): Ticker in the original format.
        
        Returns:
        str: Ticker in the desired format.
        """
        if " " not in ticker:
            return ticker
        splits =  ticker.split(" ")  # Split the ticker by spaces
        symb, date_part =splits[0], splits[-1]
        date_part = date_part.strip()
        formatted_date = date_part[2:6] +date_part[:2]   # Reformat the date part
        right = date_part[6]
        strike = int(date_part[7:])/1000
        return f"{symb}_{formatted_date}{right}{strike}".replace(".0", "")  # Combine the parts in the desired format
    
    def _convert_option_tosw(self, ticker):
            """
            Convert ticker from 'SPX_monthdayyearC110' to 'SPX yearmonthdayC00110000' format.
            
            Parameters:
            ticker (str): Ticker in the original format.
            
            Returns:
            str: Ticker in the desired format.
            """
            if "_" not in ticker:
                return ticker
            symb, date_part = ticker.split("_")  # Split the ticker by spaces
            formatted_date = date_part[4:6] + date_part[:4]   # Reformat the date part
            right = date_part[6]
            strike = f"{int(float(date_part[7:]) * 1000):08d}"
            symb = symb.split()[0].strip().ljust(6)
            return f"{symb}{formatted_date}{right}{strike}"  # Combine the parts in the desired format
        
    @retry_on_exception(sleep=1)
    def get_quotes(self, symbol:list):
        
        symbol = [self._convert_option_tosw(s) for s in symbol]
        resp = self.session.get_quotes(symbol)
        assert resp.status_code == httpx.codes.OK    

        resp = resp.json()
        quotes = {}
        for symb, vals in resp.items():
            if symb == 'errors':
                continue
            ticker = self._convert_option_fromsw(symb)
            quote = vals['quote']
            quoteTimeInLong = quote.get("tradeTime")*1000
        
            quotes[ticker] = {
                            'symbol' : ticker,
                            'description': "",
                            'askPrice': float(quote.get("askPrice")),  
                            'bidPrice': float(quote.get("bidPrice")),    
                            'lastPrice': float(quote.get("lastPrice")),
                            'quoteTimeInLong': quoteTimeInLong,
                            "status": '',
                            "OpenInterest": float(quote.get('openInterest')),  
                            "BidSize": float(quote.get('bidSize')), 
                            "AskSize": float(quote.get('askSize')), 
                            "LastSize": float(quote.get('lastSize')),
                            }
        
        for k in resp.get('errors', []):
            if k is not None:
                for symbol in resp['errors'][k]:
                    ticker = self._convert_option_fromsw(symbol)
                    quotes[ticker] = {
                                    'symbol' : ticker,
                                    'description': 'Symbol not found',
                                    'askPrice': 0,  
                                    'bidPrice': 0,    
                                    'quoteTimeInLong': 0,
                                    "status": ''
                                    }
        return quotes
    
    
    def send_order(self, new_order):
        if hasattr(new_order, 'build'):
            order_spec = new_order.build()
        else:
            order_spec = new_order
        
        resp = self.session.place_order(self.accountId, order_spec)
        
        order_id = None
        if resp.status_code in [httpx.codes.CREATED, httpx.codes.OK]:
            location = resp.headers.get('Location')
            if location:
                order_id = int(location.split('/')[-1])
        return resp.json() if resp.status_code == httpx.codes.OK and resp.content else resp, order_id

    def cancel_order(self, order_id):
        resp = self.session.cancel_order(self.accountId, int(order_id))
        return resp

    def get_orders(self):
        resp = self.session.get_orders_for_account(self.accountId)
        assert resp.status_code == httpx.codes.OK
        return resp.json()

    def get_order_info(self, order_id):  
        """
        order_status = 'REJECTED' | "FILLED" | "WORKING" | "CANCELED"
        """      
        resp = self.session.get_order(self.accountId, int(order_id))
        assert resp.status_code == httpx.codes.OK
        order_info = resp.json()
        
        if order_info.get('orderStrategyType') == "OCO":
            order_status = [
                order_info['childOrderStrategies'][0]['status'],
                order_info['childOrderStrategies'][1]['status']]
            if not order_status[0] == order_status[1]:
                print(f"OCO order status are different in ordID {order_id}: ",
                      f"{order_status[0]} vs {order_status[1]}, will try to get the filled")
            order_status = order_status[0] 
        elif order_info.get('orderStrategyType') in ['SINGLE', 'TRIGGER']:
            order_status = order_info['status']
        else:
            order_status = order_info.get('status', 'UNKNOWN')
        
        if "orderActivityCollection" in order_info.keys():
            prics = []
            for ind in order_info["orderActivityCollection"]:
                if 'executionLegs' in ind and ind['executionLegs']:
                    prics.append([ind['quantity'], ind['executionLegs'][0]['price']])
            if prics:
                n_tot = sum([i[0] for i in prics])
                order_info['price'] = sum([i[0]*i[1] for i in prics]) / n_tot if n_tot != 0 else 0
        return order_status, order_info

    def make_BTO_lim_order(self, Symbol:str, Qty:int, price:float, action="BTO", **kwarg):
        from schwab.orders.equities import equity_buy_limit, equity_sell_short_limit
        from schwab.orders.options import option_buy_to_open_limit, option_sell_to_open_limit
        from schwab.orders.common import Duration, Session
        
        Symbol = self._convert_option_tosw(Symbol)
        
        if "_" in Symbol or " " in Symbol.strip():
            if action == "BTO":
                builder = option_buy_to_open_limit(Symbol, int(Qty), float(price))
            elif action == "STO":
                builder = option_sell_to_open_limit(Symbol, int(Qty), float(price))
        else:
            if action == "BTO":
                builder = equity_buy_limit(Symbol, int(Qty), float(price))
            elif action == "STO":
                builder = equity_sell_short_limit(Symbol, int(Qty), float(price))
                
        builder.set_duration(Duration.GOOD_TILL_CANCEL)
        builder.set_session(Session.NORMAL)
        return builder

    def make_STC_lim(self, Symbol:str, Qty:int, price:float, strike=None, action="STC", **kwarg):
        from schwab.orders.equities import equity_sell_limit, equity_buy_to_cover_limit
        from schwab.orders.options import option_sell_to_close_limit, option_buy_to_close_limit
        from schwab.orders.common import Duration, Session
        
        Symbol = self._convert_option_tosw(Symbol)
        
        if "_" in Symbol or " " in Symbol.strip():
            if action == "STC":
                builder = option_sell_to_close_limit(Symbol, int(Qty), float(price))
            elif action == "BTC":
                builder = option_buy_to_close_limit(Symbol, int(Qty), float(price))
        else:
            if action == "STC":
                builder = equity_sell_limit(Symbol, int(Qty), float(price))
            elif action == "BTC":
                builder = equity_buy_to_cover_limit(Symbol, int(Qty), float(price))
                
        builder.set_duration(Duration.GOOD_TILL_CANCEL)
        builder.set_session(Session.NORMAL)
        return builder

    def make_STC_SL(self, Symbol:str, Qty:int, SL:float, strike=None, SL_stop:float=None, new_order=None, action="STC", **kwarg):
        from schwab.orders.generic import OrderBuilder
        from schwab.orders.common import Duration, Session, OrderType, OrderStrategyType
        from schwab.orders.common import OptionInstruction, EquityInstruction
        
        Symbol = self._convert_option_tosw(Symbol)
        
        builder = OrderBuilder()
        builder.set_order_strategy_type(OrderStrategyType.SINGLE)
        builder.set_duration(Duration.GOOD_TILL_CANCEL)
        builder.set_session(Session.NORMAL)
        
        if SL_stop is not None:
            builder.set_order_type(OrderType.STOP_LIMIT)
            builder.set_stop_price(float(SL_stop))
            builder.set_price(float(SL))
        else:
            builder.set_order_type(OrderType.STOP)
            builder.set_stop_price(float(SL))
            
        if "_" in Symbol or " " in Symbol.strip():
            instruction = OptionInstruction.SELL_TO_CLOSE if action == "STC" else OptionInstruction.BUY_TO_CLOSE
            builder.add_option_leg(instruction, Symbol, int(Qty))
        else:
            instruction = EquityInstruction.SELL if action == "STC" else EquityInstruction.BUY_TO_COVER
            builder.add_equity_leg(instruction, Symbol, int(Qty))
            
        return builder

    def make_Lim_SL_order(self, Symbol:str, Qty:int, PT:float, SL:float, SL_stop:float=None, new_order=None, action="STC", **kwarg):
        from schwab.orders.common import one_cancels_other
        
        limit_builder = self.make_STC_lim(Symbol, Qty, PT, action=action)
        stop_builder = self.make_STC_SL(Symbol, Qty, SL, SL_stop=SL_stop, action=action)
        
        return one_cancels_other(limit_builder, stop_builder)

    def make_STC_SL_trailstop(self, Symbol:str, Qty:int, trail_stop_const:float, new_order=None, action="STC", **kwarg):
        from schwab.orders.generic import OrderBuilder
        from schwab.orders.common import Duration, Session, OrderType, OrderStrategyType
        from schwab.orders.common import OptionInstruction, EquityInstruction
        from schwab.orders.common import StopPriceLinkBasis, StopPriceLinkType
        
        Symbol = self._convert_option_tosw(Symbol)
        
        builder = OrderBuilder()
        builder.set_order_strategy_type(OrderStrategyType.SINGLE)
        builder.set_duration(Duration.GOOD_TILL_CANCEL)
        builder.set_session(Session.NORMAL)
        builder.set_order_type(OrderType.TRAILING_STOP)
        
        builder.set_stop_price_offset(float(trail_stop_const))
        builder.set_stop_price_link_type(StopPriceLinkType.VALUE)
        
        if "_" in Symbol or " " in Symbol.strip():
            instruction = OptionInstruction.SELL_TO_CLOSE if action in ["STC", "STO"] else OptionInstruction.BUY_TO_CLOSE
            builder.add_option_leg(instruction, Symbol, int(Qty))
            builder.set_stop_price_link_basis(StopPriceLinkBasis.BID if action in ["STC", "STO"] else StopPriceLinkBasis.ASK)
        else:
            instruction = EquityInstruction.SELL if action in ["STC", "STO"] else EquityInstruction.BUY_TO_COVER
            builder.add_equity_leg(instruction, Symbol, int(Qty))
            builder.set_stop_price_link_basis(StopPriceLinkBasis.BID if action in ["STC", "STO"] else StopPriceLinkBasis.ASK)
            
        return builder