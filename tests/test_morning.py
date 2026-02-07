#!/usr/bin/env python3
"""
Test Morning Module - Complete version
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.morning import MorningSource
from channels.mock import MockChannel
from channels.pushplus import PushPlusChannel


def test_morning_mock():
    """测试完整版 morning 模块"""
    print("=== Testing Complete Morning Module ===\n")
    
    engine = Engine()
    
    # 注册
    engine.register_source('morning', MorningSource(topic='me'))
    engine.register_channel('mock', MockChannel())
    
    # 运行
    success = engine.run_source('morning', ['mock'])
    
    print(f"\n{'✅' if success else '❌'} Test completed")


if __name__ == '__main__':
    test_morning_mock()
