import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from core.env import get_env_config

def check():
    config = get_env_config()
    print(f"Detected Environment: {config.env}")
    
    token = config.get('network', 'pushplus_token')
    if not token or token.startswith("${"):
        print("❌ PUSHPLUS_TOKEN is NOT set!")
    else:
        print(f"✅ PUSHPLUS_TOKEN is found (starts with: {token[:4]}...)")
        
    github_token = config.get('github', 'token')
    if not github_token or github_token.startswith("${"):
        print("❌ GITHUB_TOKEN is NOT set! (Images won't upload)")
    else:
        print(f"✅ GITHUB_TOKEN is found")

if __name__ == "__main__":
    check()
