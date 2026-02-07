#!/usr/bin/env python3
"""
Real Stock Push - 真实股票推送
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.stock import StockSource
from channels.pushplus import PushPlusChannel


def main():
    print("=== Stock Real Push ===\n")
    
    engine = Engine()
    
    # 注册
    engine.register_source('stock', StockSource(topic='me'))
    engine.register_channel('pushplus', PushPlusChannel())
    
    # 运行
    success = engine.run_source('stock', ['pushplus'])
    
    print(f"\n{'✅ 推送成功!' if success else '❌ 推送失败'}")


if __name__ == '__main__':
    main()
