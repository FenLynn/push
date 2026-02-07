#!/usr/bin/env python3
"""
Test Stock Module
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.stock import StockSource
from channels.mock import MockChannel


def test_stock_mock():
    """测试 Stock 模块"""
    print("=== Testing Stock Module ===\n")
    
    engine = Engine()
    
    # 注册
    engine.register_source('stock', StockSource(topic='me'))
    engine.register_channel('mock', MockChannel())
    
    # 运行
    success = engine.run_source('stock', ['mock'])
    
    print(f"\n{'✅' if success else '❌'} Test completed")


if __name__ == '__main__':
    test_stock_mock()
