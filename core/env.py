"""
Environment Auto-Detection System
环境自动检测系统 - 根据主机名/IP 自动选择配置
"""
import os
import socket
import yaml
from pathlib import Path
from typing import Dict, Any


class EnvironmentDetector:
    """环境检测器 - 自动识别运行环境"""
    
    # 环境标识规则
    ENV_RULES = {
        'local': {
            'hostnames': ['py', 'localhost'],
            'ip_prefixes': ['192.168.', '127.0.0.1']
        },
        'aliyun': {
            'hostnames': ['iZuf6...', 'aliyun'],  # 阿里云主机名通常以 iZ 开头
            'ip_prefixes': ['47.', '8.']  # 阿里云公网 IP 段
        }
    }
    
    @classmethod
    def detect(cls) -> str:
        """
        检测当前环境
        
        Returns:
            str: 环境名称 (local/aliyun/unknown)
        """
        # 1. 尝试从环境变量获取（最高优先级）
        if env_override := os.getenv('PUSH_ENV'):
            return env_override.lower()
        
        # 2. 根据主机名识别
        hostname = socket.gethostname()
        for env_name, rules in cls.ENV_RULES.items():
            if hostname in rules['hostnames']:
                return env_name
        
        # 3. 根据 IP 识别
        try:
            local_ip = cls._get_local_ip()
            for env_name, rules in cls.ENV_RULES.items():
                for prefix in rules['ip_prefixes']:
                    if local_ip.startswith(prefix):
                        return env_name
        except:
            pass
        
        return 'unknown'
    
    @classmethod
    def _get_local_ip(cls) -> str:
        """获取本机 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return '127.0.0.1'


class EnvironmentConfig:
    """环境配置管理器"""
    
    def __init__(self, config_dir: str = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录（默认为 cloud/config/）
        """
        if config_dir is None:
            # 默认配置在 cloud/config/ 目录
            cloud_dir = Path(__file__).parent.parent / 'cloud' / 'config'
            config_dir = cloud_dir
        
        self.config_dir = Path(config_dir)
        self.env = EnvironmentDetector.detect()
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        # 加载默认配置
        default_config = self._load_yaml('default.yaml')
        
        # 加载环境特定配置
        env_config_file = self.config_dir / f'{self.env}.yaml'
        if env_config_file.exists():
            env_config = self._load_yaml(env_config_file)
            # 合并配置（环境配置覆盖默认配置）
            config = {**default_config, **env_config}
        else:
            print(f"[Warning] No config for environment '{self.env}', using default")
            config = default_config
        
        # 注入环境变量（最高优先级）
        config = self._inject_env_vars(config)
        
        return config
    
    def _load_yaml(self, filepath) -> Dict[str, Any]:
        """加载 YAML 文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}
    
    def _inject_env_vars(self, config: Dict) -> Dict:
        """从环境变量注入敏感配置"""
        env_map = {
            'PUSHPLUS_TOKEN': ['network', 'pushplus_token'],
            'TTRSS_PASSWORD': ['network', 'ttrss_password'],
            'SMMS_TOKEN': ['network', 'smms_token'],
            'PUSHPLUS_WEBHOOK': ['network', 'pushplus_webhook'],
            'GITHUB_TOKEN': ['github', 'token'],
            'HTTP_PROXY': ['network', 'http_proxy'],
            'HTTPS_PROXY': ['network', 'https_proxy']
        }
        
        for env_key, path in env_map.items():
            if val := os.getenv(env_key):
                # 按路径设置配置值
                current = config
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[path[-1]] = val
        
        return config
    
    def get(self, *path, default=None):
        """
        获取配置值
        
        Examples:
            config.get('network', 'ttrss_url')
            config.get('github', 'owner')
        """
        try:
            value = self.config
            for key in path:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_proxy(self):
        """设置代理（如果配置中有）"""
        if proxy := self.get('network', 'http_proxy'):
            os.environ['http_proxy'] = proxy
            os.environ['https_proxy'] = proxy
            print(f"[Config] Proxy set: {proxy}")


# 全局单例
_global_env_config = None


def get_env_config() -> EnvironmentConfig:
    """获取全局配置单例"""
    global _global_env_config
    if _global_env_config is None:
        _global_env_config = EnvironmentConfig()
        print(f"[Config] Detected environment: {_global_env_config.env}")
    return _global_env_config


if __name__ == '__main__':
    # 测试
    config = get_env_config()
    print(f"Environment: {config.env}")
    print(f"TTR RSS URL: {config.get('network', 'ttrss_url')}")
    print(f"TTR RSS Username: {config.get('network', 'ttrss_username')}")
    print(f"PushPlus Token: {config.get('network', 'pushplus_token', default='Not Set')}")
