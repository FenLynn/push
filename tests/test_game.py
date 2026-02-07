#!/usr/bin/env python3
"""
Test Game Module
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.game import GameSource
from channels.mock import MockChannel


def test_game_mock():
    """测试 Game 模块"""
    print("=== Testing Game Module ===\n")
    
    engine = Engine()
    
    # 注册
    engine.register_source('game', GameSource(topic='me'))
    engine.register_channel('mock', MockChannel())
    
    # 运行
    success = engine.run_source('game', ['mock'])
    
    print(f"\n{'✅' if success else '❌'} Test completed")


if __name__ == '__main__':
    test_game_mock()
