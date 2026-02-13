import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.d1_client import D1Client
    from dotenv import load_dotenv
    # Load .env explicitly for local run
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
except ImportError:
    print("Error importing core.d1_client. Make sure you are in the project root.")
    sys.exit(1)

def main():
    print("Initializing Cloudflare D1 Table Schema...")
    
    # Initialize D1
    # Ensure env vars are set: CLOUDFLARE_D1_ACCOUNT_ID, CLOUDFLARE_D1_DATABASE_ID, CLOUDFLARE_D1_API_TOKEN
    d1 = D1Client()
    
    if not d1.enabled:
        print("Error: Cloudflare D1 credentials not found in environment variables.")
        print("Please set: CLOUDFLARE_D1_ACCOUNT_ID, CLOUDFLARE_D1_DATABASE_ID, CLOUDFLARE_D1_API_TOKEN")
        return

    table_name = "articles"
    schema = """
    CREATE TABLE IF NOT EXISTS articles (
        id TEXT PRIMARY KEY,
        title TEXT,
        link TEXT,
        published_at TEXT,
        source_name TEXT,
        source_type TEXT,
        content TEXT,
        created_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_published ON articles(published_at);
    
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level TEXT,
        logger_name TEXT,
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        module TEXT,
        func_name TEXT,
        line_no INTEGER
    );
    """
    
    print(f"Creating table '{table_name}'...")
    res = d1.query(schema)
    
    if res.get('success'):
        print("Success! Table headers created.")
        # Verify
        check = d1.query(f"PRAGMA table_info({table_name})")
        if check.get('success'):
            print("Current columns:")
            for col in check['data'][0]['results']:
                print(f"- {col['name']} ({col['type']})")
    else:
        print(f"Failed to create table: {res.get('error')}")

if __name__ == "__main__":
    main()
