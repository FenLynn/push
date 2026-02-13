
import sys
import os
import json
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.d1_client import D1Client
from sources.finance.manager import DataManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('Push.Scripts.MigrateTags')

def migrate():
    # 1. Load Local Tags
    manager = DataManager()
    tags = manager.tags
    
    if not tags:
        logger.info("No local tags found to migrate.")
        return

    logger.info(f"Found {len(tags)} local tags. Starting migration to D1...")

    # 2. Init D1 Client
    client = D1Client()
    if not client.enabled:
        logger.error("D1 Client disabled. Cannot migrate.")
        return

    # 3. Iterate and Upload
    success_count = 0
    fail_count = 0

    for name, data in tags.items():
        url = data.get('url')
        raw_date = data.get('date')
        
        if not url or not raw_date:
            logger.warning(f"Skipping {name}: incomplete data")
            continue

        # Standardize date (remove milliseconds)
        try:
            # Try parsing with various formats if needed, but usually it's ISO like
            # If it contains '.', split it
            if '.' in raw_date:
                clean_date = raw_date.split('.')[0]
            else:
                clean_date = raw_date
            
            # Verify it's a valid format (optional, but good for safety)
            # datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S") 
            # actually some dates might be just YYYY-MM-DD, let's keep them as is if simple
            
        except Exception as e:
            logger.warning(f"Date parse error for {name} ({raw_date}): {e}")
            clean_date = raw_date

        # SQL: INSERT OR REPLACE
        sql = "INSERT OR REPLACE INTO finance_tags (name, url, date) VALUES (?, ?, ?)"
        params = [name, url, clean_date]
        
        res = client.query(sql, params)
        if res.get('success'):
            logger.info(f"✅ Migrated {name}")
            success_count += 1
        else:
            logger.error(f"❌ Failed {name}: {res.get('error')}")
            fail_count += 1

    logger.info(f"Migration Complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    migrate()
