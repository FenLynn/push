#!/usr/bin/env python3
"""
Real Morning Push - 真实早报推送
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.morning import MorningSource
from channels.pushplus import PushPlusChannel


def main():
    print("=== Morning Real Push ===\n")
    
    engine = Engine()
    
    # 注册
    engine.register_source('morning', MorningSource(topic='me'))
    engine.register_channel('pushplus', PushPlusChannel())
    
    # 运行
    success = engine.run_source('morning', ['pushplus'])
    
    print(f"\n{'✅ 推送成功!' if success else '❌ 推送失败'}")


if __name__ == '__main__':
    main()
