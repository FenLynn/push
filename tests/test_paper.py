#!/usr/bin/env python3
"""
Test Paper Module
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.paper import PaperSource
from channels.mock import MockChannel


def test_paper_mock():
    """测试 Paper 模块"""
    print("=== Testing Paper Module ===\n")
    
    engine = Engine()
    
    # 注册
    engine.register_source('paper', PaperSource(topic='me'))
    engine.register_channel('mock', MockChannel())
    
    # 运行
    success = engine.run_source('paper', ['mock'])
    
    print(f"\n{'✅' if success else '❌'} Test completed")


if __name__ == '__main__':
    test_paper_mock()
