import configparser
import os
from typing import Dict, List, Any

class ConfigLoader:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance.config = configparser.ConfigParser()
            # Support case-sensitive keys if needed, but default is insensitive
            cls._instance.config.optionxform = str 
            cls._instance.load()
        return cls._instance

    def load(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(f"[Debug] base_dir={base_dir}, abspath={os.path.abspath(__file__)}")
        print(f"[Debug] base_dir={base_dir}, abspath={os.path.abspath(__file__)}")
        
        # Priority 1: .private/config.ini (recommended for security)
        private_config = os.path.join(base_dir, '.private', 'config.ini')
        # Priority 2: config.ini (legacy, backward compatible)
        root_config = os.path.join(base_dir, 'config.ini')
        
        config_path = private_config if os.path.exists(private_config) else root_config
        
        if os.path.exists(config_path):
            self.config.read(config_path, encoding='utf-8')
            print(f"[Config] Loaded from: {config_path}")
        else:
            print(f"[Config] Warning: No config file found. Tried {private_config} and {root_config}")

    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)

    def get_section(self, section) -> Dict[str, str]:
        """Return a dictionary of keys/values in a section"""
        if self.config.has_section(section):
            return dict(self.config.items(section))
        return {}

    def get_damai_venues(self, city_code) -> List[Dict[str, str]]:
        """
        Special helper for Damai venues.
        Reads [damai.places.{city_code}]
        Returns list of {'id': '...', 'name': '...'}
        """
        section = f"damai.places.{city_code}"
        matches = self.get_section(section)
        venues = []
        for vid, name in matches.items():
            venues.append({'id': vid, 'name': name})
        return venues
    
    def get_etf_list(self) -> List[str]:
        """
        Get list of ETF codes from [finance.etf]
        """
        targets = self.get('finance.etf', 'targets', fallback='')
        if targets:
            return [c.strip() for c in targets.split(',') if c.strip()]
        return []

    
    def get_stock_watchlist(self) -> List[tuple]:
        """
        Get stock watchlist as [(Name, Code), ...]
        Reads [finance.stock]
        """
        section = self.get_section('finance.stock')
        # Return as list of (Name, Code) to match legacy format
        # INI format: Code = Name
        return [(name, code) for code, name in section.items()]

    def get_stock_etf_watchlist(self) -> List[tuple]:
        """
        Get stock ETF watchlist as [(Name, Code), ...]
        Reads [finance.stock_etf]
        """
    def get_llm_config(self) -> Dict[str, str]:
        """
        Get LLM config from [llm] section or env vars
        """
        conf = self.get_section('llm')
        
        # Env vars override
        provider = os.getenv('LLM_PROVIDER', conf.get('provider', 'zhipu'))
        api_key = os.getenv('LLM_API_KEY', conf.get('api_key', ''))
        base_url = os.getenv('LLM_BASE_URL', conf.get('base_url', ''))
        model = os.getenv('LLM_MODEL', conf.get('model', ''))
        proxy = os.getenv('LLM_PROXY', conf.get('proxy', ''))
        
        return {
            'provider': provider,
            'api_key': api_key,
            'base_url': base_url,
            'model': model,
            'proxy': proxy
        }



        
# Global instance
config = ConfigLoader()
