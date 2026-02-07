import sys
import os

# 确保导入路径正确
sys.path.insert(0, os.path.abspath('.'))

from sources.morning.source import MorningSource
from channels.mock import MockChannel

def test_morning_optimized():
    print("Testing Optimized Morning Module...")
    source = MorningSource(topic='me')
    channel = MockChannel()
    
    # 模拟运行
    msg = source.run()
    
    print(f"\nTitle: {msg.title}")
    print(f"Type: {msg.type}")
    print(f"Content Length: {len(msg.content)} bytes")
    
    # 打印前 500 个字符预览 HTML
    print("\nHTML Preview (First 500 chars):")
    print(msg.content[:500] + "...")
    
    # 验证关键部分是否存在于 HTML 中
    checks = ['早报', '📅 基本信息', '☀️ 城市天气', 'card']
    for check in checks:
        if check in msg.content:
            print(f"✓ Found: {check}")
        else:
            print(f"✗ Missing: {check}")

if __name__ == "__main__":
    test_morning_optimized()
