import os 
import configparser 
from pathlib import Path

import logging 

#__all__=['global_config','root_path','package_name','pic_type']

class ConfigLoader():
    """支持多级配置加载的全局管理器"""
    def __init__(self):
        self.config  = configparser.ConfigParser()
        # 加载模块内置默认配置 
        #print (__file__)
        module_path = Path(__file__).parent / 'utils/default.ini' 
        self.config.read(module_path) 
        #print (module_path)
        # 加载用户自定义配置（优先级更高）
        if custom_config := os.getenv('CLOUD_CONFIG'): 
            self.config.read(custom_config)
            
        # 注入环境变量 (覆盖配置文件中的敏感信息)
        self._inject_env_vars()

    def _inject_env_vars(self):
        """从环境变量注入敏感配置"""
        env_map = {
            'PUSHPLUS_TOKEN': ('NETWORK', 'PUSHPLUS_TOKEN'),
            'TTRSS_PASSWORD': ('NETWORK', 'TTRSSPASSWORD'),
            'SMMS_TOKEN': ('NETWORK', 'SMMS_TOKEN'),
            'PUSHPLUS_WEBHOOK': ('NETWORK', 'PUSHPLUS_WEBHOOK'),
            'GITHUB_TOKEN': ('GITHUB', 'TOKEN')
        }
        for env_key, (section, key) in env_map.items():
            if val := os.getenv(env_key):
                if not self.config.has_section(section):
                    self.config.add_section(section)
                self.config.set(section, key, val) 
 
    def get(self, section, key):
        """安全获取配置参数"""
        return self.config.get(section,  key, fallback=None)
    
    def getint(self, section, key):
        """安全获取配置参数"""
        return self.config.getint(section,  key, fallback=None)
    
    def getfloat(self, section, key):
        """安全获取配置参数"""
        return self.config.getfloat(section,  key, fallback=None)
    
    def getboolean(self, section, key):
        """安全获取配置参数"""
        return self.config.getboolean(section,  key, fallback=None)
 
 
global_config = ConfigLoader()

## 
root_path = os.path.abspath(os.path.dirname(__file__))
package_name=__package__

## pic generate info
utils_path=root_path+'/utils/'
pic_type=global_config.get('PIC','TYPE')
pic_path=utils_path
pic_width1=global_config.getint('PIC','WIDTH1')
pic_height1=global_config.getint('PIC','HEIGHT1')
pic_width2=global_config.getint('PIC','WIDTH2')
pic_height2=global_config.getint('PIC','HEIGHT2')
pic_dpi=global_config.getint('PIC','DPI')

## github  info
g_token=global_config.get('GITHUB','TOKEN')
g_owner=global_config.get('GITHUB','OWNER')
g_repo=global_config.get('GITHUB','REPO')
g_branch=global_config.get('GITHUB','BRANCH')
g_cdn=global_config.get('GITHUB','CDN').split(',')

## finance
gdsm_stock_list=global_config.get('FINANCE','GDSMSTOCKLIST').split(',')
stock_diy_list=global_config.get('FINANCE','STOCK_ID').split(',')
index_diy_list=global_config.get('FINANCE','INDEX_ID').split(',')
stock_name_diy_list=global_config.get('FINANCE','STOCK_NAME').split(',')
bold_stock_list=global_config.get('FINANCE','BOLD_STOCK').split(',')
hk_stock_list=global_config.get('FINANCE','HK_STOCK_ID').split(',')


## TTRSS
ttrss_url=global_config.get('NETWORK','TTRSSURL')
ttrss_username=global_config.get('NETWORK','TTRSSUSERNAME')
ttrss_password=global_config.get('NETWORK','TTRSSPASSWORD')

## format
css_file=global_config.get('TEXT','CSSFILE')


## pushplus
p_token=global_config.get('NETWORK','PUSHPLUS_TOKEN').split(',')
p_webhook=global_config.get('NETWORK','PUSHPLUS_WEBHOOK')

## 
server_ip=global_config.get('NETWORK','SERVER_IP').split(',')
proxy_ip=global_config.get('NETWORK','PROXY').split(',')
smms_token=global_config.get('NETWORK','SMMS_TOKEN')
vps_proxy_ip=global_config.get('NETWORK','VPS_PROXY')
font_path = global_config.get('HOST','FONT_PATH')

## 
stopword=global_config.get('TEXT','STOPWORD').split(',')

log_level = logging.getLevelName(global_config.get('LOGGING','LEVEL').upper()) 
logging.basicConfig(level = log_level ,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')  #logging.INFO
mylog = logging.getLogger(__name__)
mylog.debug(f'Logging level: {log_level}')

is_use_proxy=0
is_vps=1
