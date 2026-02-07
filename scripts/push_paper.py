#!/usr/bin/env python3
"""
Real Paper Push - 真实论文推送
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.paper import PaperSource
from channels.pushplus import PushPlusChannel


def main():
    print("=== Paper Real Push ===\n")
    
    engine = Engine()
    
    # 注册
    engine.register_source('paper', PaperSource(topic='me'))
    engine.register_channel('pushplus', PushPlusChannel())
    
    # 运行
    success = engine.run_source('paper', ['pushplus'])
    
    print(f"\n{'✅ 推送成功!' if success else '❌ 推送失败'}")


if __name__ == '__main__':
    main()
