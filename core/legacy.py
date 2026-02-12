
"""
Legacy Adapter Module
Replacing 'cloud' package imports with 'core' equivalents.
"""
from core.config import config
# Expose config vars as globals to match cloud.config
p_token = [] # Deprecated
server_ip = [] # Deprecated
font_path = config.root_path + '/core/utils/msyh.ttc'
root_path = config.root_path

from core.utils.net import *
from core.env import get_env_config
from core.utils.time import *
from core.utils.math import *
from core.utils.tool import *
from core.utils.lib import *
from core.utils.game_scraper import get_game_schedule
from core.image_upload import upload_image_to_github, upload_image_with_cdn, upload_image_to_cdn

# Legacy proxy variables
is_use_proxy = config.get('NETWORK', 'PROXY', fallback='') != ''
vps_proxy_ip = config.get('NETWORK', 'VPS_PROXY', fallback='')
bold_stock_list = config.get_bold_stocks()

# Helpers
is_local = lambda: not is_server()

__all__ = [
    'get_env_config', 'is_server', 'is_local', 'get_host_ip',
    'upload_image_to_cdn', 'upload_image_to_smms',
    'get_game_schedule', 'is_use_proxy', 'vps_proxy_ip', 'bold_stock_list',
    'get_today_trade_status', 'get_trade_day'
]
from core.utils.plot import *

# Aliases for backward compatibility
upload_image_to_smms = upload_image_with_cdn
