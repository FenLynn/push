"""
Archive Source: Tech (Trends)
Fetches Top Hacker News Story and archives it to local SQLite.
Replacement for flaky GitHub scraper.
"""
import requests
import pandas as pd
import datetime
import logging
from sources.base import BaseSource
from core import Message, ContentType
from core.db import db

class ArchiveTechSource(BaseSource):
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        self.logger = logging.getLogger('Push.Source.ArchiveTech')
        self.table_name = "tech_news_daily"

    def run(self) -> Message:
        self.logger.info("Archiving Tech Data (Hacker News)...")
        
        data = []
        summary = "No data"
        
        try:
            # 1. Get Top Stories IDs
            top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            resp = requests.get(top_url, timeout=10)
            if resp.status_code == 200:
                top_ids = resp.json()
                if top_ids:
                    # 2. Get #1 Story Details
                    story_id = top_ids[0]
                    item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    item_resp = requests.get(item_url, timeout=10)
                    
                    if item_resp.status_code == 200:
                        story = item_resp.json()
                        title = story.get('title', 'Unknown')
                        url = story.get('url', '')
                        score = story.get('score', 0)
                        
                        record = {
                            'date': datetime.date.today().isoformat(),
                            'rank': 1,
                            'title': title,
                            'url': url,
                            'score': score,
                            'source': 'HackerNews',
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                        data.append(record)
                        summary = f"#1 HN: {title} ({score} pts)"
        except Exception as e:
            self.logger.error(f"Failed to fetch Hacker News: {e}")
            summary = f"Error: {e}"

        # Save to SQLite
        if data:
            df = pd.DataFrame(data)
            db.save_monitor_data(df, self.table_name, if_exists='append', unique_index=['date', 'source', 'rank'])
            
        return Message(
            title=f"Tech Archive (HN)",
            content=summary,
            type=ContentType.MARKDOWN,
            tags=['archive', 'tech']
        )
