#!/usr/bin/env python3
"""
Unified Entry Point for Push Project
Usage:
    python main.py run all              # Run all modules
    python main.py run morning paper    # Run specific modules
    python main.py list                 # List available modules
    python main.py run estate --topic family
"""
import sys
import os
import argparse
import time
import warnings

# Suppress py_mini_racer UserWarning from akshare
warnings.filterwarnings("ignore", category=UserWarning, module='py_mini_racer')

# Ensure project root is in path
# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Simple .env loader
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()
    except Exception as e:
        print(f"Warning: Failed to load .env: {e}")

from core.engine import Engine
from channels.pushplus import PushPlusChannel

from sources.finance import FinanceSource

# Import Sources
from sources.morning import MorningSource
from sources.paper import PaperSource
from sources.game import GameSource
from sources.stock import StockSource
from sources.night import NightSource
from sources.fund import FundSource
from sources.life import LifeSource
from sources.etf import ETFSource
from sources.estate import EstateSource
from sources.damai import DamaiSource

from sources.archive.env import ArchiveEnvSource
from sources.archive.ops import ArchiveOpsSource
from sources.archive.tech import ArchiveTechSource
from sources.archive.vps import ArchiveVPSSource
from sources.report.weekly import WeeklyReportSource

import logging
from core.logger import setup_logger

# Task Scheduler for execution tracking
from core.task_scheduler import get_scheduler

MODULES = {
    'morning': {'class': MorningSource, 'desc': '早报 (天气/金融/英语)'},
    'paper':   {'class': PaperSource,   'desc': '论文 (TTR RSS)'},
    'finance': {'class': FinanceSource, 'desc': '财经日报 (宏观/市场)'},
    'game':    {'class': GameSource,    'desc': '游戏赛程'},
    'stock':   {'class': StockSource,   'desc': '股票行情'},
    'night':   {'class': NightSource,   'desc': '美股夜盘'},
    'fund':    {'class': FundSource,    'desc': '基金估值'},
    'life':    {'class': LifeSource,    'desc': '影视数据'},
    'etf':     {'class': ETFSource,     'desc': 'ETF监控'},
    'estate':  {'class': EstateSource,  'desc': '成都房产'},
    'damai':   {'class': DamaiSource,   'desc': '大麦演出'},
    'archive_env': {'class': ArchiveEnvSource, 'desc': '环境存档 (天气/AQI)'},
    'archive_ops': {'class': ArchiveOpsSource, 'desc': '资产存档 (域名/SSL)'},
    'archive_tech': {'class': ArchiveTechSource, 'desc': '科技存档 (HackerNews)'},
    'archive_vps': {'class': ArchiveVPSSource, 'desc': '主机存档 (性能监控)'},
    'report_weekly': {'class': WeeklyReportSource, 'desc': '周报总结 (Weekly Museum)'},
}

# Group Presets for easy push
#   usage: python main.py run @stock
GROUPS = {
    'me':     ['morning', 'finance', 'paper'],      # 默认个人组
    'stock':  ['finance', 'stock', 'etf', 'fund'],  # 股票相关
    'paper':  ['paper'],                             # 论文类
    'baobao': ['morning', 'game', 'life'],          # 宝宝组
    'family': ['morning', 'estate'],                # 家庭组
    'night':  ['night'],                             # 美股组
    'archive': ['archive_env', 'archive_ops', 'archive_tech', 'archive_vps'], # 存档组
    'all':    list(MODULES.keys()),                  # 所有模块
}

def list_modules():
    """List available modules and groups"""
    print("\n=== Available Modules ===")
    for name, info in MODULES.items():
        print(f"  {name:10s} - {info['desc']}")
    print("\n=== Group Presets (use @groupname) ===")
    for name, mods in GROUPS.items():
        print(f"  @{name:10s} - {', '.join(mods)}")

def get_engine(token=None, require_channel=True):
    engine = Engine()
    try:
        channel = PushPlusChannel(token=token)
        engine.register_channel('pushplus', channel)
    except ValueError:
        if require_channel:
            raise
        # If not requiring channel (e.g. gen mode), just ignore
        pass
    return engine

def gen_modules(modules_to_run, topic='me', token=None):
    """Generate content only"""
    logger = logging.getLogger('Push.CLI')
    logger.info(f"=== Generate Only ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===")
    
    engine = get_engine(token, require_channel=False)
    
    for name in modules_to_run:
        module_key = name
        extra_kwargs = {}
        
        # Support module:arg syntax
        if ':' in name:
            base, arg = name.split(':', 1)
            # Find matching module
            if base in MODULES:
                module_key = base
                # Special handling for known parameterized modules
                if base == 'damai':
                    extra_kwargs['city_code'] = arg
        
        if module_key not in MODULES:
            logger.error(f"Error: Unknown module '{name}'")
            continue
            
        info = MODULES[module_key]
        logger.info(f"Generating {module_key} ({extra_kwargs if extra_kwargs else 'default'})...")
        kwargs = {'topic': topic}
        if 'args' in info: kwargs.update(info['args'])
        kwargs.update(extra_kwargs)
        
        try:
            source = info['class'](**kwargs)
            engine.register_source(name, source)
            path = engine.run_source_only(name)
            if path:
                logger.info(f"✅ Generated: {path}")
        except Exception as e:
            logger.error(f"Failed to generate {name}: {e}")

def run_modules(modules_to_run, topic='me', token=None, title=None):
    """Generate and Send (Standard Run)"""
    logger = logging.getLogger('Push.CLI')
    logger.info(f"=== Push Run ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===")
    
    engine = get_engine(token)
    success_count = 0
    
    # Get scheduler for tracking
    scheduler = get_scheduler()
    scheduler.plan_day()  # Ensure today's plan exists
    
    for name in modules_to_run:
        module_key = name
        extra_kwargs = {}
        
        # Support module:arg syntax
        if ':' in name:
            base, arg = name.split(':', 1)
            if base in MODULES:
                module_key = base
                if base == 'damai':
                    extra_kwargs['city_code'] = arg
        
        if module_key not in MODULES:
            continue
        
        # Check if should run based on scheduler
        if not scheduler.should_run_today(module_key):
            logger.info(f"Skipping {module_key} (condition not met today)")
            scheduler.record_skip(module_key, "条件不满足")
            continue
            
        info = MODULES[module_key]
        logger.info(f"Running {module_key} ({extra_kwargs if extra_kwargs else 'default'})...")
        kwargs = {'topic': topic}
        if 'args' in info: kwargs.update(info['args'])
        kwargs.update(extra_kwargs)
        
        # Record start
        scheduler.record_start(module_key)
            
        try:
            # 1. 初始化源
            source = info['class'](**kwargs)
            engine.register_source(name, source)
            
            # 2. 生成消息
            results = source.run()
            if not isinstance(results, list):
                results = [results]
            
            for idx, message in enumerate(results):
                # 3. 覆盖标题 (如果指定)
                if title:
                    logger.info(f"Overriding title to: {title}")
                    message.title = title
                    if len(results) > 1:
                        message.title += f" ({idx+1}/{len(results)})"
                
                # 4. 推送
                # Use None to send to all registered channels
                if engine.run_with_message(message, name, channel_names=None):
                    success_count += 1
            
            # Record success
            scheduler.record_success(module_key)
            
        except Exception as e:
            logger.critical(f"Error running {name}: {e}", exc_info=True)
            # Record failure
            scheduler.record_failure(module_key, str(e))
            
    logger.info(f"Summary: {success_count}/{len(modules_to_run)} modules succeeded")

def send_file(file_path, title=None, token=None):
    """Send content from an existing file"""
    import os
    from core import Message, ContentType
    
    logger = logging.getLogger('Push.CLI')
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return
        
    logger.info(f"Sending file: {file_path}")
    
    # Read content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check type
    if file_path.endswith('.html'):
        c_type = ContentType.HTML
    else:
        c_type = ContentType.MARKDOWN
        
    # Default title if not provided
    if not title:
        fname = os.path.basename(file_path)
        title = f"File Push: {fname}"
        
    msg = Message(
        title=title,
        content=content,
        type=c_type,
        tags=['manual', 'file']
    )
    
    # Send
    engine = get_engine(token)
    # We call channel send directly or use engine splitter? 
    # Engine logic is better for uniformity (splitting etc)
    # But Engine needs a Source. We can mock one or just use channel directly.
    # Using channel directly for simplicity here.
    
    # Actually, let's use engine's splitter logic just in case file is huge
    # Send using Engine's broadcast capability
    # We use a dummy source name 'manual'
    if engine.run_with_message(msg, 'manual', channel_names=None):
         logger.info("✅ Sent successfully to all channels")
    else:
         logger.error("❌ Send failed (check logs)")

def main():
    setup_logger('Push')
    parser = argparse.ArgumentParser(description="Push Project Unified CLI")
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Common Args
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--topic', default='me', help='Topic (default: me)')
    common.add_argument('--token', help='PushPlus Token (override)')
    
    # 1. RUN (Default)
    run_parser = subparsers.add_parser('run', parents=[common], help='Generate AND Send')
    run_parser.add_argument('modules', nargs='+', help='Module names (or "all")')
    run_parser.add_argument('--title', help='Override notification title')
    
    # 2. GEN (Generate Only)
    gen_parser = subparsers.add_parser('gen', parents=[common], help='Generate Only (Save to output/)')
    gen_parser.add_argument('modules', nargs='+', help='Module names (or "all")')
    
    # 3. SEND (File Only or Module Latest)
    send_parser = subparsers.add_parser('send', parents=[common], help='Send existing file or latest module output')
    group = send_parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', help='Path to file to send')
    group.add_argument('module', nargs='?', help='Module name to send latest output for')
    send_parser.add_argument('--title', help='Custom title')
    
    # 4. LIST
    subparsers.add_parser('list', help='List available modules')
    
    args = parser.parse_args()
    
    # Logic
    if args.command == 'list':
        list_modules()
        return
        
    if args.command == 'send':
        if args.file:
            send_file(args.file, title=args.title, token=args.token)
        elif args.module:
            if args.module not in MODULES:
                print(f"Error: Unknown module '{args.module}'")
                return
            
            # Auto-detect latest file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            latest_path = os.path.join(base_dir, 'output', args.module, 'latest.html')
            
            if not os.path.exists(latest_path):
                print(f"Error: No latest output found for {args.module} at {latest_path}")
                print(f"Please run 'python main.py gen {args.module}' first.")
                return
                
            # Default title if not provided
            if not args.title:
                # Try to extract title from HTML? Or just use "Latest {Module}"
                args.title = f"Latest {args.module.capitalize()} (Re-push)"
            
            send_file(latest_path, title=args.title, token=args.token)
        return
    # For Run/Gen, parse modules
    if args.command in ['run', 'gen']:
        # Expand group presets
        mods = []
        for m in args.modules:
            if m.startswith('@'):
                group_name = m[1:]
                if group_name in GROUPS:
                    mods.extend(GROUPS[group_name])
                else:
                    print(f"Unknown group: {m}")
            elif m == 'all':
                mods.extend(MODULES.keys())
            else:
                mods.append(m)
        mods = list(dict.fromkeys(mods))  # Remove duplicates, preserve order
        
        if args.command == 'run':
            run_modules(mods, topic=args.topic, token=args.token, title=args.title)
        else:
            gen_modules(mods, topic=args.topic, token=args.token)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
