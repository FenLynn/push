#!/usr/bin/env python3
"""
Real Etf Push
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.etf import ETFSource
from channels.pushplus import PushPlusChannel

def main():
    print("=== Etf Real Push ===")
    engine = Engine()
    engine.register_channel('pushplus', PushPlusChannel())
    
    source = ETFSource(topic='me')
    engine.register_source('etf', source)
    
    engine.run_source('etf', ['pushplus'])

if __name__ == '__main__':
    main()
