#!/usr/bin/env python3
"""Test 6 Modules - Night/Fund/Life/ETF/Estate/Damai"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.engine import Engine
from sources.night import NightSource
from sources.fund import FundSource
from sources.life import LifeSource
from sources.etf import ETFSource
from sources.estate import EstateSource
from sources.damai import DamaiSource
from channels.mock import MockChannel

def test_all():
    print("=" * 50)
    print("Testing 6 Modules (Mock)")
    print("=" * 50 + "\n")
    
    engine = Engine()
    engine.register_channel('mock', MockChannel())
    
    modules = [
        ('night', NightSource(topic='me'), '美股夜盘'),
        ('fund', FundSource(topic='me'), '基金估值'),
        ('life', LifeSource(topic='me'), '影视数据'),
        ('etf', ETFSource(topic='me'), 'ETF监控'),
        ('estate', EstateSource(topic='me'), '成都房产'),
        ('damai', DamaiSource(topic='me', city='成都'), '大麦演出'),
    ]
    
    results = []
    for name, source, desc in modules:
        print(f"\n{'='*40}")
        print(f"Testing {desc} ({name})")
        print('='*40)
        engine.register_source(name, source)
        success = engine.run_source(name, ['mock'])
        results.append((desc, success))
    
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    for desc, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {desc}")

if __name__ == '__main__':
    test_all()
