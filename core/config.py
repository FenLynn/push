import configparser
import os
from typing import Dict, List, Any

class ConfigLoader:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance.config = configparser.ConfigParser()
            cls._instance.config.optionxform = str
            cls._instance.load()
        return cls._instance

    def load(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Priority 1: config/*.ini (Git tracked modular configs)
        config_dir = os.path.join(base_dir, 'config')
        if os.path.exists(config_dir):
            for filename in sorted(os.listdir(config_dir)):
                if filename.endswith('.ini'):
                    self.config.read(os.path.join(config_dir, filename), encoding='utf-8')

        # Priority 2: config.ini (Legacy/Public Root)
        root_config = os.path.join(base_dir, 'config.ini')
        if os.path.exists(root_config):
            self.config.read(root_config, encoding='utf-8')

        # Priority 3: .private/config.ini (Private Override)
        private_config = os.path.join(base_dir, '.private', 'config.ini')
        if os.path.exists(private_config):
            self.config.read(private_config, encoding='utf-8')

    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)

    def get_section(self, section) -> Dict[str, str]:
        if self.config.has_section(section):
            return dict(self.config.items(section))
        return {}

    def get_damai_venues(self, city_code) -> List[Dict[str, str]]:
        section = f"damai.places.{city_code}"
        matches = self.get_section(section)
        return [{'id': vid, 'name': name} for vid, name in matches.items()]

    def get_damai_cities(self) -> Dict[str, str]:
        """Get configured cities and their codes"""
        # New mode: [damai.cities] name = code
        section = 'damai.cities'
        if self.config.has_section(section):
            return dict(self.config.items(section))
        return {}
    
    def get_etf_list(self) -> List[str]:
        targets = self.get('finance.etf', 'targets', fallback='')
        return [c.strip() for c in targets.split(',') if c.strip()]
    
    def get_stock_watchlist(self) -> List[tuple]:
        section = self.get_section('finance.stock')
        return [(name, code) for code, name in section.items()]

    def get_stock_etf_watchlist(self) -> List[tuple]:
        section = self.get_section('finance.stock_etf')
        return [(name, code) for code, name in section.items()]

    def get_llm_config(self) -> Dict[str, str]:
        conf = self.get_section('llm')
        return {
            'provider': os.getenv('LLM_PROVIDER', conf.get('provider', 'zhipu')),
            'api_key': os.getenv('LLM_API_KEY', conf.get('api_key', '')),
            'base_url': os.getenv('LLM_BASE_URL', conf.get('base_url', '')),
            'model': os.getenv('LLM_MODEL', conf.get('model', '')),
            'proxy': os.getenv('LLM_PROXY', conf.get('proxy', ''))
        }

config = ConfigLoader()
