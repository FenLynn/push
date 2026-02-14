"""
Archive Source: Ops (Assets)
Checks Domain & SSL expiry and archives it to local SQLite.
"""
import ssl
import socket
import pandas as pd
import datetime
import logging
from sources.base import BaseSource
from core import Message, ContentType
from core.db import db

class ArchiveOpsSource(BaseSource):
    def __init__(self, topic='me', **kwargs):
        super().__init__(**kwargs)
        self.topic = topic
        self.logger = logging.getLogger('Push.Source.ArchiveOps')
        # TODO: Load from config/env in future
        self.domains = ["baidu.com", "google.com", "bing.com"] 
        self.table_name = "ops_domain_status"

    def run(self) -> Message:
        self.logger.info("Archiving Ops Data...")
        
        data = []
        summary_lines = []
        
        for domain in self.domains:
            res = {
                'date': datetime.date.today().isoformat(),
                'domain': domain,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # SSL Check
            try:
                context = ssl.create_default_context()
                with socket.create_connection((domain, 443), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=domain) as ssock:
                        cert = ssock.getpeercert()
                        # Date format: 'Feb 12 12:00:00 2026 GMT'
                        expiry = datetime.datetime.strptime(cert['notAfter'], r'%b %d %H:%M:%S %Y %Z')
                        days_left = (expiry - datetime.datetime.now()).days
                        
                        res['ssl_days'] = days_left
                        res['ssl_expiry'] = expiry.strftime('%Y-%m-%d')
                        res['status'] = 'OK'
                        
                        summary_lines.append(f"🟢 {domain}: {days_left} days left")
            except Exception as e:
                self.logger.warning(f"SSL Check failed for {domain}: {e}")
                res['ssl_days'] = -1
                res['ssl_expiry'] = None
                res['status'] = 'Error'
                summary_lines.append(f"🔴 {domain}: Error ({str(e)[:20]}...)")
            
            data.append(res)

        # Save to SQLite
        if data:
            df = pd.DataFrame(data)
            db.save_monitor_data(df, self.table_name, if_exists='append', unique_index=['date', 'domain'])
            
        return Message(
            title=f"Ops Archive ({len(data)} domains)",
            content="\n".join(summary_lines),
            type=ContentType.MARKDOWN,
            tags=['archive', 'ops']
        )
