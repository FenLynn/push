"""
Report Source: Weekly Intelligence (The "Museum" View)
Aggregates data from Archive modules (Tech, Life, Ops) into a rich HTML report.
Features:
- Tech: Top Hacker News stories of the week.
- Ops: VPS Health Trends (CPU/RAM) charts (Base64 embedded).
- Life: Weather summary.
- Assets: Domain/SSL status.
"""
import pandas as pd
import datetime
import logging
import io
import base64
import matplotlib.pyplot as plt
from sources.base import BaseSource
from core import Message, ContentType
from core.db import db

class WeeklyReportSource(BaseSource):
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        self.logger = logging.getLogger('Push.Source.ReportWeekly')
        
    def run(self) -> Message:
        self.logger.info("Generating Weekly Intelligence Report...")
        
        # 1. Define Time Range (Last 7 Days)
        today = datetime.date.today()
        start_date = today - datetime.timedelta(days=7)
        
        context = {
            'date_range': f"{start_date} ~ {today}",
            'tech_stories': self._get_tech_stories(start_date),
            'vps_chart': self._generate_vps_chart(start_date),
            'weather_summary': self._get_weather_summary(start_date),
            'asset_status': self._get_asset_status(),
        }
        
        # 2. Render Report
        # Simple HTML construction for now (can move to template later)
        html_content = self._render_html(context)
        
        return Message(
            title=f"周报: 数字生活馆 ({today})",
            content=html_content,
            type=ContentType.HTML,
            tags=['report', 'weekly']
        )

    def _get_tech_stories(self, start_date):
        """Get top HN stories from last week"""
        try:
            df = db.get_monitor_data("tech_news_daily", limit=50, order_by="date DESC")
            if df.empty: return []
            df['date'] = pd.to_datetime(df['date']).dt.date
            mask = (df['date'] >= start_date)
            return df[mask].to_dict('records')
        except: return []

    def _get_weather_summary(self, start_date):
        """Get weather summary"""
        try:
            df = db.get_monitor_data("life_weather_daily", limit=50, order_by="date DESC")
            if df.empty: return []
            df['date'] = pd.to_datetime(df['date']).dt.date
            mask = (df['date'] >= start_date)
            # Group by city
            start_date_str = start_date.isoformat()
            
            summary = []
            for city in df['city'].unique():
                city_df = df[(df['city'] == city) & mask]
                if not city_df.empty:
                    avg_temp = round(city_df['temp_avg'].mean(), 1)
                    summary.append(f"{city}: Avg {avg_temp}°C")
            return ", ".join(summary)
        except: return "No Data"

    def _get_asset_status(self):
        """Get latest asset status"""
        try:
            df = db.get_monitor_data("ops_domain_status", limit=20, order_by="date DESC")
            if df.empty: return []
            # Dedup by domain, keep latest
            df = df.sort_values('date', ascending=False).drop_duplicates('domain')
            return df.to_dict('records')
        except: return []

    def _generate_vps_chart(self, start_date):
        """Generate HTML/CSS Bar Chart for VPS Health"""
        try:
            df = db.get_monitor_data("ops_vps_daily", limit=14, order_by="date DESC")
            if df.empty: return ""
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Filter for range
            mask = (df['date'].dt.date >= start_date)
            df = df[mask]
            if df.empty: return ""
            
            html_rows = ""
            for _, row in df.iterrows():
                date_str = row['date'].strftime('%m-%d')
                cpu = row['cpu_load_1m']
                ram = row['mem_percent']
                
                # Normalize CPU (assuming 4 cores max for visual 100%?) 
                # Display bar width relative to 100%
                cpu_width = min(cpu * 20, 100) # Arbitrary scaling: 1.0 load = 20% width
                ram_width = min(ram, 100)
                
                html_rows += f"""
                <tr>
                    <td style='width:50px; font-size:12px;'>{date_str}</td>
                    <td>
                        <div style='display:flex; align-items:center; margin-bottom:2px;'>
                            <span style='font-size:10px; width:30px;'>CPU</span>
                            <div style='background:#3498db; width:{cpu_width}%; height:8px; border-radius:4px;'></div>
                            <span style='font-size:10px; margin-left:5px;'>{cpu}</span>
                        </div>
                        <div style='display:flex; align-items:center;'>
                            <span style='font-size:10px; width:30px;'>RAM</span>
                            <div style='background:#e74c3c; width:{ram_width}%; height:8px; border-radius:4px;'></div>
                            <span style='font-size:10px; margin-left:5px;'>{ram}%</span>
                        </div>
                    </td>
                </tr>
                """
            
            return f"""
            <table style="width:100%; border-collapse: collapse;">
                {html_rows}
            </table>
            """
            
        except Exception as e:
            self.logger.error(f"Chart error: {e}")
            return f"<p>Chart Error: {e}</p>"

    def _render_html(self, ctx):
        """Render simple HTML report"""
        
        tech_rows = ""
        for item in ctx['tech_stories']:
            # Truncate title
            title = item['title'][:50] + "..." if len(item['title']) > 50 else item['title']
            tech_rows += f"<li><span style='color:#999; font-size:12px;'>[{item['date']}]</span> <a href='{item.get('url')}' style='text-decoration:none; color:#333;'>{title}</a></li>"
            
        asset_rows = ""
        for item in ctx['asset_status']:
            color = "green" if item['status'] == 'OK' else "red"
            asset_rows += f"<tr><td>{item['domain']}</td><td>{item.get('ssl_days', 'N/A')}d</td><td style='color:{color}'>{item['status']}</td></tr>"
            
        chart_html = ctx['vps_chart'] or "<p>No Data</p>"
        
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <h2 style="margin:0; font-size:18px; color:#2c3e50;">Weekly Intelligence</h2>
                <p style="margin:5px 0 0 0; font-size:12px; color:#7f8c8d;">{ctx['date_range']}</p>
            </div>
            
            <h3 style="border-left: 4px solid #3498db; padding-left: 10px; font-size: 16px;">1. Server Health</h3>
            {chart_html}
            
            <h3 style="border-left: 4px solid #2ecc71; padding-left: 10px; font-size: 16px; margin-top:20px;">2. Assets Status</h3>
            <table style="width:100%; text-align:left; font-size:14px; border-collapse: collapse;">
                <tr style="border-bottom:1px solid #eee; color:#7f8c8d;"><th style="padding:5px;">Domain</th><th>Expires</th><th>Status</th></tr>
                {asset_rows}
            </table>

            <h3 style="border-left: 4px solid #f1c40f; padding-left: 10px; font-size: 16px; margin-top:20px;">3. Tech Trends</h3>
            <ul style="padding-left: 20px; font-size:14px; line-height:1.6;">{tech_rows}</ul>
            
            <div style="margin-top:20px; padding-top:10px; border-top:1px solid #eee; text-align:center; font-size:12px; color:#95a5a6;">
                <p>Weather: {ctx['weather_summary']}</p>
                <p>Generated by Push Service</p>
            </div>
        </div>
        """
