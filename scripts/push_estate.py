#!/usr/bin/env python3
"""
Real Estate Push
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.estate import EstateSource
from channels.pushplus import PushPlusChannel

def main():
    print("=== Estate Real Push ===")
    engine = Engine()
    engine.register_channel('pushplus', PushPlusChannel())
    
    source = EstateSource(topic='me')
    engine.register_source('estate', source)
    
    engine.run_source('estate', ['pushplus'])

if __name__ == '__main__':
    main()
