import shutil
import os
import pandas as pd
import datetime
import logging
import matplotlib.pyplot as plt
from sources.base import BaseSource
from core import Message, ContentType
from core.db import db
from core.image_upload import upload_image_with_cdn

class ArchiveVPSSource(BaseSource):
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        self.logger = logging.getLogger('Push.Source.ArchiveVPS')
        self.table_name = "ops_vps_daily"

    def run(self) -> Message:
        self.logger.info("Archiving VPS Stats...")
        
        try:
            # 1. Collect Data
            total_d, used_d, free_d = shutil.disk_usage("/")
            disk_percent = round((used_d / total_d) * 100, 1)
            
            mem_info = self._get_mem_info()
            mem_percent = 0
            if mem_info['total'] > 0:
                mem_percent = round(((mem_info['total'] - mem_info['available']) / mem_info['total']) * 100, 1)
                
            cpu_load = round(os.getloadavg()[0], 2)
            
            record = {
                'date': datetime.date.today().isoformat(),
                'cpu_load_1m': cpu_load,
                'mem_percent': mem_percent,
                'disk_percent': disk_percent,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # 2. Save to SQLite
            df_new = pd.DataFrame([record])
            db.save_monitor_data(df_new, self.table_name, if_exists='append', unique_index=['date'])
            
            # 3. Generate Chart (7-Day Trend)
            chart_url = self._generate_chart()
            
            # 4. Construct Message
            summary = f"**CPU Load**: {cpu_load} | **RAM**: {mem_percent}% | **Disk**: {disk_percent}%"
            content = f"{summary}\n\n"
            if chart_url:
                content += f"![VPS Trend]({chart_url})"
            
            return Message(
                title="VPS Health Monitor",
                content=content,
                type=ContentType.MARKDOWN,
                tags=['archive', 'vps']
            )
            
        except Exception as e:
            self.logger.error(f"VPS Monitor Failed: {e}", exc_info=True)
            return Message(
                title="VPS Archive Error",
                content=str(e),
                type=ContentType.TEXT
            )

    def _generate_chart(self):
        """Generate trend chart for last 7 days"""
        try:
            # Fetch data
            df = db.get_monitor_data(self.table_name, limit=14, order_by="date DESC")
            if df.empty:
                return None
                
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date') # Ascending for plot
            
            # Plot
            plt.figure(figsize=(10, 4), dpi=100)
            
            # Dual Axis
            ax1 = plt.gca()
            ax2 = ax1.twinx()
            
            # Plot CPU (Left Axis)
            l1 = ax1.plot(df['date'], df['cpu_load_1m'], 'b-o', label='CPU Load (1m)', linewidth=2)
            ax1.set_ylabel('Load Avg', color='b')
            ax1.tick_params(axis='y', labelcolor='b')
            
            # Plot RAM (Right Axis)
            l2 = ax2.plot(df['date'], df['mem_percent'], 'r--s', label='RAM %', linewidth=2)
            ax2.set_ylabel('RAM %', color='r')
            ax2.tick_params(axis='y', labelcolor='r')
            ax2.set_ylim(0, 100)
            
            # Title & Grid
            plt.title('VPS Performance Trend (Last 14 Days)')
            ax1.grid(True, linestyle='--', alpha=0.5)
            
            # Date formatting
            import matplotlib.dates as mdates
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            plt.gcf().autofmt_xdate()
            
            # Legend
            lines = l1 + l2
            labels = [l.get_label() for l in lines]
            ax1.legend(lines, labels, loc='upper left')
            
            # Save
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'output', 'archive_vps')
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            img_path = os.path.join(output_dir, f"vps_trend_{datetime.date.today()}.png")
            plt.savefig(img_path, bbox_inches='tight')
            plt.close()
            
            # Upload
            return upload_image_to_cdn(img_path)
            
        except Exception as e:
            self.logger.error(f"Chart generation failed: {e}")
            return None

    def _get_mem_info(self):
        """Read /proc/meminfo"""
        mem = {'total': 0, 'available': 0}
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal' in line:
                        mem['total'] = int(line.split()[1])
                    elif 'MemAvailable' in line:
                        mem['available'] = int(line.split()[1])
        except:
            pass
        return mem
