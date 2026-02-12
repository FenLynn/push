import sys
import os
import logging

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import Message, ContentType
from channels.pushplus import PushPlusChannel
from dotenv import load_dotenv

# Load env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
# Also try loading from core.config if needed, but .env is standard

def run_push():
    # 1. Read HTML
    html_path = "/nfs/python/push/output/paper/latest.html"
    if not os.path.exists(html_path):
        print(f"Error: {html_path} not found")
        return

    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 2. Create Message
    msg = Message(
        title="光学文献(UI预览)",
        content=html_content,
        type=ContentType.HTML
    )

    # 3. Setup Channel
    token = os.getenv('PUSHPLUS_TOKEN')
    print(f"Token present: {bool(token)}")
    
    if not token:
        # Try to find it in config/default.ini or main.py logic?
        # For now, let's assume it's in env or we can hardcode if user provided it (user didn't).
        # We can try to read from legacy config if needed.
        from core.config import config
        # Attempt to read from config if defined
        pass

    try:
        channel = PushPlusChannel(token=token, topic='paper')
        print("Sending...")
        success = channel.send(msg)
        if success:
            print("Push success!")
        else:
            print("Push failed.")
    except Exception as e:
        print(f"Error during push: {e}")

if __name__ == "__main__":
    run_push()
