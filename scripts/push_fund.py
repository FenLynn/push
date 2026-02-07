#!/usr/bin/env python3
"""
Real Fund Push
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.fund import FundSource
from channels.pushplus import PushPlusChannel

def main():
    print("=== Fund Real Push ===")
    engine = Engine()
    engine.register_channel('pushplus', PushPlusChannel())
    
    source = FundSource(topic='me')
    engine.register_source('fund', source)
    
    engine.run_source('fund', ['pushplus'])

if __name__ == '__main__':
    main()
