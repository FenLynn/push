#!/usr/bin/env python3
"""
Demo script - Test the new IFTTT architecture
"""
import sys
import os

# Add push directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.morning import MorningSource
from channels.mock import MockChannel
from channels.pushplus import PushPlusChannel


def test_with_mock():
    """使用 Mock Channel 测试"""
    print("=== Testing with Mock Channel ===\n")
    
    # 创建引擎
    engine = Engine()
    
    # 注册组件
    engine.register_source('morning', MorningSource())
    engine.register_channel('mock', MockChannel())
    
    # 运行
    success = engine.run_source('morning', ['mock'])
    
    print(f"\n✅ Test completed, success={success}")


def test_with_pushplus(topic='me'):
    """使用真实 PushPlus 测试"""
    print("=== Testing with PushPlus ===\n")
    
    # 创建引擎
    engine = Engine()
    
    # 注册组件
    engine.register_source('morning', MorningSource())
    
    try:
        engine.register_channel('pushplus', PushPlusChannel(topic=topic))
    except ValueError as e:
        print(f"❌ PushPlus配置错误: {e}")
        print("请设置环境变量 PUSHPLUS_TOKEN")
        return False
    
    # 运行
    success = engine.run_source('morning', ['pushplus'])
    
    print(f"\n{'✅' if success else '❌'} Test completed")
    return success


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test IFTTT architecture')
    parser.add_argument('--mode', choices=['mock', 'real'], default='mock',
                        help='Test mode (mock or real)')
    parser.add_argument('--topic', default='me',
                        help='PushPlus topic (default: me)')
    
    args = parser.parse_args()
    
    if args.mode == 'mock':
        test_with_mock()
    else:
        test_with_pushplus(args.topic)
