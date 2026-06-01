
import unittest
import sys
from unittest.mock import MagicMock, patch

# Mock google.generativeai BEFORE importing the module that uses it
sys.modules['google'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()

# Now we can safely import
from DiscordAlertsTrader.llm_parser import LLMMessageParser

class TestLLMParser(unittest.TestCase):
    def test_mock_parsing(self):
        # Mock the config using ConfigParser
        import configparser
        mock_cfg = configparser.ConfigParser()
        mock_cfg.add_section('llm')
        mock_cfg.set('llm', 'enable_llm_parsing', 'True')
        mock_cfg.set('llm', 'provider', 'google')
        mock_cfg.set('llm', 'api_key', 'dummy')
        mock_cfg.set('llm', 'model_name', 'gemini-pro')
        
        with patch('DiscordAlertsTrader.llm_parser.cfg', mock_cfg), patch('DiscordAlertsTrader.llm_parser.genai.Client') as MockClient:
            import DiscordAlertsTrader.llm_parser as lp
            lp.has_genai = True
            # Setup the LLM parser
            parser = LLMMessageParser(cfg=mock_cfg)
            
            # Mock the model instance and response
            mock_model = MagicMock()
            mock_response = MagicMock()
            mock_response.text = '```json\n{"action": "BTO", "Symbol": "AAPL", "Qty": 10, "price": 150.0, "asset": "stock"}\n```'
            mock_model.generate_content.return_value = mock_response
            
            # Inject our mock model
            parser.client.models.generate_content.return_value = mock_response
            
            # Run the method
            result = parser.parse_trade_alert("Buy 10 AAPL at 150")
            
            # Verify
            self.assertIsNotNone(result)
            self.assertEqual(result['action'], 'BTO')
            self.assertEqual(result['Symbol'], 'AAPL')
            self.assertEqual(result['Qty'], 10)
            self.assertEqual(result['price'], 150.0)

if __name__ == '__main__':
    unittest.main()
