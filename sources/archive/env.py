"""
Archive Source: Environment (Life)
Fetches Weather & AQI data and archives it to local SQLite.
"""
import requests
import pandas as pd
import datetime
import logging
from sources.base import BaseSource
from core import Message, ContentType
from core.db import db  # SQLite Instance

class ArchiveEnvSource(BaseSource):
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        self.logger = logging.getLogger('Push.Source.ArchiveEnv')
        self.cities = ["Chengdu", "Xian"]
        self.table_name = "life_weather_daily"

    def run(self) -> Message:
        self.logger.info("Archiving Environment Data...")
        
        data = []
        summary_lines = []
        
        for city in self.cities:
            try:
                # wttr.in format: %t (temp) %p (precip) %l (location)
                # Using JSON format j1
                url = f"https://wttr.in/{city}?format=j1"
                resp = requests.get(url, timeout=15)
                
                if resp.status_code == 200:
                    j = resp.json()
                    current = j['current_condition'][0]
                    
                    record = {
                        'date': datetime.date.today().isoformat(),
                        'city': city,
                        'temp_C': int(current['temp_C']),
                        'desc': current['weatherDesc'][0]['value'],
                        'humidity': float(current['humidity']),
                        'uv_index': int(current.get('uvIndex', 0)),
                        'timestamp': datetime.datetime.now().isoformat()
                    }
                    data.append(record)
                    summary_lines.append(f"{city}: {record['temp_C']}°C {record['desc']}")
                    
            except Exception as e:
                self.logger.error(f"Failed to fetch weather for {city}: {e}")
                summary_lines.append(f"{city}: Error")

        # Save to SQLite
        if data:
            df = pd.DataFrame(data)
            # Use 'city' + 'date' as unique key to prevent duplicates on same day
            db.save_monitor_data(df, self.table_name, if_exists='append', unique_index=['date', 'city'])
            
        return Message(
            title=f"Environment Archive ({len(data)} cities)",
            content="\n".join(summary_lines),
            type=ContentType.MARKDOWN,
            tags=['archive', 'env']
        )
