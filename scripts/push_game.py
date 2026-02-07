#!/usr/bin/env python3
"""
Real Game Push - 真实游戏赛程推送
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.game import GameSource
from channels.pushplus import PushPlusChannel


def main():
    print("=== Game Real Push ===\n")
    
    engine = Engine()
    
    # 注册
    engine.register_source('game', GameSource(topic='me'))
    engine.register_channel('pushplus', PushPlusChannel())
    
    # 运行
    success = engine.run_source('game', ['pushplus'])
    
    print(f"\n{'✅ 推送成功!' if success else '❌ 推送失败'}")


if __name__ == '__main__':
    main()
