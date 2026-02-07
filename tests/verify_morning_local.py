import sys
import os
import logging

# Setup Text Logging
logging.basicConfig(level=logging.INFO)

sys.path.insert(0, os.path.abspath('.'))
from sources.morning.source import MorningSource

def generate_local_preview():
    print("🚀 Starting Morning Report Generation...")
    
    source = MorningSource(topic='me')
    
    # 1. Gather Data (Debug Mode)
    # We call the internal method to inspect raw data first
    print("\n[Debug] Gathering Data...")
    try:
        context = source._gather_data()
        
        # Print Debug Info
        print(f"  - Date Info: {context.get('date_info')}")
        print(f"  - Weather Keys: {list(context.get('weather', {}).keys())}")
        print(f"  - Index Keys: {context.get('index', {}).keys() if context.get('index') is not None else 'None'}")
        print(f"  - Gold Keys: {context.get('gold', {}).keys() if context.get('gold') is not None else 'None'}")
        
    except Exception as e:
        print(f"❌ Error gathering data: {e}")
        return

    # 2. Render HTML
    print("\n[Debug] Rendering HTML...")
    try:
        # Re-run full logic to get the final message object
        # Note: run() calls _gather_data() again, but that's fine for testing
        msg = source.run()
        
        output_file = "preview_morning.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(msg.content)
            
        print(f"\n✅ HTML Generated: {os.path.abspath(output_file)}")
        print(f"Size: {len(msg.content)} bytes")
        
        # Preview first 500 chars
        print("\n--- HTML Preview (Head) ---")
        print(msg.content[:500])
        print("---------------------------")
        
    except Exception as e:
        print(f"❌ Error rendering HTML: {e}")

if __name__ == "__main__":
    generate_local_preview()
