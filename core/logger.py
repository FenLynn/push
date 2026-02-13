"""
Core Logger - 统一日志管理
"""
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler

def setup_logger(name='Push', log_dir='logs', level=logging.INFO):
    """
    配置并获取 logger
    
    Args:
        name: Logger 名称
        log_dir: 日志目录
        level: 日志级别
        
    Returns:
        logging.Logger: 配置好的 logger
    """
    # 确保日志目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    
    # 避免重复添加 Handler
    if logger.handlers:
        return logger
        
    # 格式器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 1. Console Handler (标准输出)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 2. Handler based on RUN_MODE
    from .config import config
    
    if config.RUN_MODE == 'cloud':
        # Cloud Mode: Console + D1 (Error only)
        # Avoid local file logging in cloud (usually read-only or ephemeral)
        try:
            from .cloud_logger import D1LogHandler
            d1_handler = D1LogHandler()
            d1_handler.setFormatter(formatter)
            d1_handler.setLevel(logging.ERROR) # Only push errors to DB
            logger.addHandler(d1_handler)
        except Exception as e:
            # Fallback to console if D1 fails init
            print(f"Failed to init D1LogHandler: {e}")
            
    else:
        # Local/Docker Mode: Console + File
        log_file = os.path.join(log_dir, 'app.log')
        try:
            file_handler = TimedRotatingFileHandler(
                log_file,
                when='midnight',
                interval=1,
                backupCount=30,  # 保留30天
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            # In some docker envs, log_dir might not be writable?
            pass
    
    return logger
