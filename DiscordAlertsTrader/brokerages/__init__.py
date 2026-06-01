import sys
try:
    import paho.mqtt.client as mqtt
except ImportError:
    import types
    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.on_connect = None
            self.on_subscribe = None
            self.on_unsubscribe = None
            self.on_message = None
        def tls_set_context(self, *args, **kwargs):
            pass
        def username_pw_set(self, *args, **kwargs):
            pass
        def connect(self, *args, **kwargs):
            return 0
        def loop_start(self, *args, **kwargs):
            pass
        def subscribe(self, *args, **kwargs):
            pass
        def unsubscribe(self, *args, **kwargs):
            pass
        def loop(self, *args, **kwargs):
            pass
        def loop_forever(self, *args, **kwargs):
            pass
    paho_mod = types.ModuleType('paho')
    mqtt_mod = types.ModuleType('paho.mqtt')
    client_mod = types.ModuleType('paho.mqtt.client')
    client_mod.Client = DummyClient
    mqtt_mod.client = client_mod
    paho_mod.mqtt = mqtt_mod
    sys.modules['paho'] = paho_mod
    sys.modules['paho.mqtt'] = mqtt_mod
    sys.modules['paho.mqtt.client'] = client_mod

from abc import ABC, abstractmethod
from ..configurator import cfg
import time
import functools

def retry_on_exception(retries=2, do_raise=False, sleep=False):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, retries+1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"Exception occurred: {e}. Retrying... (Attempt {attempt}/{retries})")
                    if sleep:
                        time.sleep(1)
            if do_raise:
                raise Exception(f"Method {func.__name__} failed after {retries} retries.")
            else:
                print(f"Method {func.__name__} failed after {retries} retries. Returning...")
        return wrapper
    return decorator


class BaseBroker(ABC):
    @abstractmethod
    def __init__(self, api_key, secret_key, passphrase):
        pass

    @abstractmethod
    def get_session(self):
        pass

    @abstractmethod
    def get_quotes(self, symbol):
        pass

    @abstractmethod
    def send_order(self, side, symbol, order_type, quantity, price=None, stop_price=None):
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    @abstractmethod
    def get_orders(self):
        pass

    @abstractmethod
    def get_order_info(self, order_id):
        pass


def get_brokerage(name=cfg['general']['BROKERAGE']):
    if not name or str(name).lower() in ['', 'none']:
        return None
    name = str(name)
    try:
        if name.lower() == 'tda':
            from .TDA_api import TDA
            accountId = cfg['TDA']['accountId']
            accountId = None if len(accountId) == 0 else accountId
            tda = TDA(accountId=accountId)
            tda.get_session()
            return tda
        elif name.lower() == 'schwab':  
            from .schwab_api import SW
            sc = SW()
            sc.get_session()
            return sc
        elif name.lower() == 'tradestation':
            from .tradestation_api import TS
            accountId = cfg['tradestation']['accountId']
            accountId = None if len(accountId) == 0 else accountId
            ts = TS(accountId=accountId)
            ts.get_session()
            return ts
        elif name.lower() == "webull":
            from .weBull_api import weBull
            wb = weBull(cfg['webull'].getboolean('paper'))
            success = wb.get_session()
            if success:
                return wb
            else:
                print("\n[WARNING] Webull session initialization returned False.")
                return None
        elif name.lower() == 'etrade':
            from .eTrade_api import eTrade
            accountId = cfg['etrade']['accountId']
            accountId = None if len(accountId) == 0 else accountId
            et = eTrade(accountId=accountId)
            try:
                et.get_session()
            except Exception as e:
                print("Got error: \n", e, "\n Trying again...if it fails again, rerun the application.")
                et.get_session()
            return et
        elif name.lower() == 'ibkr':
            from .ibkr_api import IBKR
            accountId = cfg['IBKR']['accountId']
            accountId = None if len(accountId) == 0 else accountId
            ibkr = IBKR(accountId=accountId)
            ibkr.get_session()
            return ibkr
    except Exception as e:
        print(f"\n[WARNING] Failed to initialize brokerage '{name}': {e}")
        print("Continuing application startup with brokerage integration disabled (bksession = None).\n")
        return None