#!/usr/bin/env python3
"""
Real Damai Push
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.damai import DamaiSource
from channels.pushplus import PushPlusChannel

def main():
    print("=== Damai Real Push ===")
    engine = Engine()
    engine.register_channel('pushplus', PushPlusChannel())
    
    source = DamaiSource(topic='me', city='成都')
    engine.register_source('damai', source)
    
    engine.run_source('damai', ['pushplus'])

if __name__ == '__main__':
    main()
