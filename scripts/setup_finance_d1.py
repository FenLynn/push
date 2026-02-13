
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.d1_client import D1Client

def setup_d1():
    client = D1Client()
    if not client.enabled:
        print("Error: D1 Client not enabled. Check credentials.")
        return

    # Schema: name (PK), url, date (YYYY-MM-DD HH:MM:SS)
    schema = """
    CREATE TABLE IF NOT EXISTS finance_tags (
        name TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        date TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    print("Creating table 'finance_tags'...")
    res = client.query(schema)
    if res['success']:
        print("✅ Table 'finance_tags' created/verified successfully.")
    else:
        print(f"❌ Failed to create table: {res.get('error')}")

if __name__ == "__main__":
    setup_d1()
