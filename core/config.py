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
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 1. Load Default Config (Source of Truth)
        default_config = os.path.join(self.base_dir, 'config', 'default.ini')
        if os.path.exists(default_config):
            self.config.read(default_config, encoding='utf-8')
        else:
            # Fallback for development if default.ini moved
            pass

        # 2. Load Personal Override (Optional)
        personal_config = os.path.join(self.base_dir, '.private', 'personal.ini')
        if os.path.exists(personal_config):
            self.config.read(personal_config, encoding='utf-8')
            
    @property
    def root_path(self) -> str:
        return self.base_dir

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

    def get_bold_stocks(self) -> List[str]:
        val = self.get('FINANCE', 'BOLD_STOCK', fallback='')
        return [s.strip() for s in val.split(',') if s.strip()]

    def get_hk_stock_list(self) -> List[str]:
        val = self.get('FINANCE', 'HK_STOCK_ID', fallback='')
        return [s.strip() for s in val.split(',') if s.strip()]

    def get_llm_config(self) -> Dict[str, str]:
        conf = self.get_section('llm')
        return {
            'provider': os.getenv('LLM_PROVIDER', conf.get('provider', 'zhipu')),
            'api_key': os.getenv('LLM_API_KEY', conf.get('api_key', '')),
            'base_url': os.getenv('LLM_BASE_URL', conf.get('base_url', '')),
            'model': os.getenv('LLM_MODEL', conf.get('model', '')),
            'proxy': os.getenv('LLM_PROXY', conf.get('proxy', ''))
        }

    @property
    def ops_domains(self) -> List[str]:
        domains = self.get('OPS', 'DOMAINS', fallback='')
        return [d.strip() for d in domains.split(',') if d.strip()]

    @property
    def RUN_MODE(self) -> str:
        """
        Determines the current execution mode.
        Returns:
            - 'cloud': GitHub Actions or other serverless env
            - 'docker': Running inside a Docker container
            - 'local': Local development (default)
        """
        # 1. Explicit override
        if os.getenv('RUN_MODE'):
            return os.getenv('RUN_MODE').lower()
        # 2. GitHub Actions
        if os.getenv('GITHUB_ACTIONS') == 'true':
            return 'cloud'
        # 3. Docker
        if os.path.exists('/.dockerenv') or os.getenv('AM_I_IN_A_DOCKER_CONTAINER') == 'true':
            return 'docker'
        return 'local'

config = ConfigLoader()
