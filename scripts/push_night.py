#!/usr/bin/env python3
"""
Real Night Push
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine
from sources.night import NightSource
from channels.pushplus import PushPlusChannel

def main():
    print("=== Night Real Push ===")
    engine = Engine()
    engine.register_channel('pushplus', PushPlusChannel())
    
    source = NightSource(topic='me')
    engine.register_source('night', source)
    
    engine.run_source('night', ['pushplus'])

if __name__ == '__main__':
    main()
