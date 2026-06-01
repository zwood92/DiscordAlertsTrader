
import os
import json
import re
from typing import Optional, Dict, Any, List
try:
    from google import genai
    has_genai = True
except ImportError:
    class DummyGenai:
        class Client:
            def __init__(self, *args, **kwargs):
                pass
    genai = DummyGenai
    has_genai = False
from DiscordAlertsTrader.configurator import cfg

class LLMMessageParser:
    def __init__(self, cfg: Dict[str, Any] = cfg):
        self.cfg = cfg
        self.enabled = cfg['llm'].getboolean('enable_llm_parsing')
        if self.enabled and not has_genai:
            print("Warning: LLM parsing enabled but 'google-genai' library is not installed.")
            self.enabled = False
        self.provider = cfg['llm']['provider']
        self.api_key = cfg['llm']['api_key']
        self.model_name = cfg['llm']['model_name']
        
        if self.enabled:
            self._setup_client()

    def _setup_client(self):
        if self.provider == 'google':
            api_key = self.api_key or os.getenv('GOOGLE_API_KEY')
            if not api_key:
                print("Warning: LLM parsing enabled but no GOOGLE_API_KEY found.")
                self.enabled = False
                return
            self.client = genai.Client(api_key=api_key)
        elif self.provider == 'openai':
            # Future implementation
            pass

    def parse_trade_alert(self, message: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None

        from datetime import datetime
        current_date = datetime.now().strftime("%m/%d")
        current_year = datetime.now().year

        prompt = f"""
        You are a trading assistant. Extract the following trade details from the user's message into JSON format.
        
        Current Date: {current_date}/{current_year}
        
        Message: "{message}"
        
        Required Fields:
        - action: BTO (Buy Open), STC (Sell Close), STO (Sell Open), BTC (Buy Close), or ExitUpdate
        - Symbol: Ticker symbol (e.g., AAPL, TSLA)
        - Qty: Quantity (integer or null)
        - price: Price (float or null)
        - asset: 'stock' or 'option'
        
        Optional Fields (for Options):
        - strike: e.g., "150C" or "150P". If call/put not specified, assume Call (C).
        - expDate: Expiration date in MM/DD format. Resolve relative dates like "next week", "tomorrow", "odte" (0 days to expiry / today) based on Current Date.
        
        Optional Fields (Risk/Exits):
        - risk: 'high', 'medium', 'lotto', etc.
        - PT1, PT2, PT3: Profit targets (e.g., "1.5" or "50%")
        - SL: Stop loss (e.g., "1.0" or "20%")
        
        Return ONLY the JSON object, no markdown formatting.
        """
        
        try:
            response = self.client.models.generate_content(model=self.model_name, contents=prompt)
            data = self._clean_json(response.text)
            
            # Post-processing to match expected format
            if data.get('asset') == 'option':
                # Ensure strike has C/P
                if data.get('strike') and not (data['strike'].upper().endswith('C') or data['strike'].upper().endswith('P')):
                     data['strike'] += 'C' # Default to Call if unknown
                
                # Format symbol for internal system: TICKER_MMDDYY[C/P]STRIKE
                # This requires more complex date logic usually handled by regex parser
                # For now, we return the dict and let the trader handle it or fail gracefully if partial
                pass
                
            return data
        except Exception as e:
            print(f"LLM Parsing Error: {e}")
            return None

    def _clean_json(self, text: str) -> Dict[str, Any]:
        text = re.sub(r'```json\s*|\s*```', '', text)
        start = text.find('{')
        end = text.rfind('}') + 1
        return json.loads(text[start:end])
