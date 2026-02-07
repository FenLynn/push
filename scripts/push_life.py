#!/usr/bin/env python3
"""
Real Life Push
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.life import LifeSource
from channels.pushplus import PushPlusChannel

def main():
    print("=== Life Real Push ===")
    engine = Engine()
    engine.register_channel('pushplus', PushPlusChannel())
    
    source = LifeSource(topic='me')
    engine.register_source('life', source)
    
    engine.run_source('life', ['pushplus'])

if __name__ == '__main__':
    main()
