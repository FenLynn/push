"""
Daily Estate Crawler Runner
每日房产数据爬虫运行器

This script runs both Chengdu and Xi'an crawlers and updates the history files.
Can be called from cron or manually.
"""
import asyncio
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def run_all():
    print("=" * 60)
    print("Running Daily Real Estate Crawlers")
    print("=" * 60)
    
    # Import and run Chengdu crawler
    try:
        from scripts.crawl_chengdu import main as chengdu_main
        await chengdu_main()
    except Exception as e:
        print(f"[ERROR] Chengdu crawler failed: {e}")
    
    print()
    
    # Import and run Xi'an crawler
    try:
        from scripts.crawl_xian import main as xian_main
        await xian_main()
    except Exception as e:
        print(f"[ERROR] Xi'an crawler failed: {e}")
    
    print()
    print("=" * 60)
    print("Crawling complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_all())
