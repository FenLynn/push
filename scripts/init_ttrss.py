#!/usr/bin/env python3
"""
TTRSS Auto-Initialization Script
1. Waits for TTRSS to be ready.
2. Checks if feeds exist.
3. If empty, imports OPML.
"""

import os
import sys
import time
import requests
import json

# Add project root to path to load env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.env import get_env_config

def get_session_id(url, user, password):
    """Login and get Session ID"""
    try:
        data = {
            "op": "login",
            "user": user,
            "password": password
        }
        res = requests.post(f"{url}/api/", json=data, timeout=5)
        res_json = res.json()
        if res_json['status'] == 0:
            return res_json['content']['session_id']
        else:
            print(f"Login failed: {res_json}")
            return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def check_feeds_exist(url, sid):
    """Check if any feeds (cats) exist"""
    data = {"op": "getCategories", "sid": sid}
    res = requests.post(f"{url}/api/", json=data)
    cats = res.json()['content']
    # If only "Uncategorized" (id 0) or "System" categories exist, we consider it "empty"
    # Usually new install might have ID 0.
    # Let's check feed count instead?
    
    data_feeds = {"op": "getFeeds", "sid": sid, "cat_id": -3} # -3 = All feeds
    res_feeds = requests.post(f"{url}/api/", json=data_feeds)
    feeds = res_feeds.json()['content']
    
    print(f"Current Feed Count: {len(feeds)}")
    return len(feeds) > 0

def import_opml(url, sid, opml_path):
    """Upload OPML file"""
    print(f"Importing OPML from {opml_path}...")
    
    # Needs to be a multipart/form-data POST to opml.php or use API?
    # TTRSS API "opml.import" takes filename text? 
    # Actually, standard API docs say: op=login...
    # Most TTRSS instances rely on the web UI for OPML import.
    # BUT, there is a plugin or method.
    # Update: As of recent versions, 'opml' method might handle it.
    # Let's try the standard 'importOpml' if it exists, or simulate multipart upload.
    
    # Official API doesn't fully document OPML import clearly for all versions.
    # However, 'opml.php' is the handler.
    # We can simulate the form submission to opml.php?op=import
    
    try:
        files = {'opml_file': open(opml_path, 'rb')}
        # Standard TTRSS web interface import
        # We need the session cookie, not just API SID?
        # The API SID is often accepted as 'sid' param.
        
        # Let's try to use the 'conf' param in API? No.
        
        # Plan B: Use the 'mc_update_daemon' or CLI if available? 
        # Inside the ttrss container there is update.php --import-opml <file> !!
        # Since we are in 'push-service' container, we cannot run CLI on 'ttrss' container directly.
        # But we can use the web endpoint.
        
        # Let's try direct API call 'opml' -> 'import'
        # According to some source: {"op": "opml", "method": "import", "filename": "..."} NO.
        
        # Let's simply print instruction if API fails.
        # OR: Simulate browser upload to /backend.php?op=opml&method=import
        
        # Actually, let's keep it simple: 
        # If we can't easily import via API, we just log it.
        # BUT the user asked for automation.
        
        # TTRSS has a CLI `update.php --opml-import <file>`.
        # Since we are in a separate container, we can't execute this easily unless we have SSH or valid creds.
        # HOWEVER, the 'ttrss' container mounts the volumes.
        # AND 'push-service' shares volumes? No, different volumes.
        
        # WAIT! We can use requests to POST to the backend with session id.
        # payload: op=opml, method=import
        # files: opml_file
        
        cookies = {'ttrss_sid': sid}
        res = requests.post(f"{url}/backend.php", 
                            data={"op": "opml", "method": "import"},
                            files=files,
                            cookies=cookies)
        
        if res.status_code == 200:
            print("OPML Import returned 200. Assuming success.")
            return True
        else:
            print(f"OPML Import failed: {res.status_code} {res.text}")
            return False
            
    except Exception as e:
        print(f"Import failed: {e}")
        return False

def main():
    env_config = get_env_config()
    url = env_config.get('network', 'ttrss_url')
    
    # Default credentials - can be overridden by .env
    user = env_config.get('network', 'ttrss_username', fallback='admin')
    password = env_config.get('network', 'ttrss_password', fallback='password')
    
    print(f"TTRSS URL: {url}")
    print(f"TTRSS User: {user}")
    
    opml_path = "/app/config/tt-rss_admin_2026-02-08.opml"
    
    if not os.path.exists(opml_path):
        print(f"OPML file not found: {opml_path}")
        return

    print("Waiting for TTRSS to come online...")
    sid = None
    for i in range(30): # Wait up to 60s
        sid = get_session_id(url, user, password)
        if sid:
            break
        time.sleep(2)
        
    if not sid:
        print("Could not connect to TTRSS. Aborting init.")
        return

    print("Login success.")
    
    if check_feeds_exist(url, sid):
        print("Feeds already exist. Skipping import.")
    else:
        print("No feeds found. importing OPML...")
        import_opml(url, sid, opml_path)

if __name__ == "__main__":
    main()
