#!/usr/bin/env python3
"""
Daily Summary Report Script
每日摘要报告脚本 - 23:00 运行

功能：
1. 汇总当天所有模块的执行状态
2. 识别应运行但未运行的模块
3. 通过 PushPlus 推送摘要报告
"""
import sys
import os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.task_scheduler import get_scheduler
from core.trading_calendar import get_trading_status
from channels.pushplus import PushPlusChannel
from core import Message, ContentType

def generate_summary_html(summary: dict) -> str:
    """生成摘要 HTML"""
    
    # 状态颜色
    def status_color(status):
        return {
            'success': '#27ae60',
            'failed': '#e74c3c',
            'pending': '#f39c12',
            'skipped': '#95a5a6',
        }.get(status, '#333')
    
    # 状态图标
    def status_icon(status):
        return {
            'success': '✅',
            'failed': '❌',
            'pending': '⏳',
            'skipped': '⏸️',
        }.get(status, '•')
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 10px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header .date {{ opacity: 0.9; font-size: 14px; margin-top: 5px; }}
            .stats {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
            .stat {{ background: #f8f9fa; padding: 15px; border-radius: 8px; flex: 1; min-width: 80px; text-align: center; }}
            .stat .value {{ font-size: 28px; font-weight: bold; }}
            .stat .label {{ font-size: 12px; color: #666; }}
            .stat.success .value {{ color: #27ae60; }}
            .stat.failed .value {{ color: #e74c3c; }}
            .stat.pending .value {{ color: #f39c12; }}
            .context {{ background: #e8f4f8; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            .context span {{ margin-right: 15px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f9fa; }}
            .status-badge {{ padding: 3px 8px; border-radius: 4px; font-size: 12px; color: white; }}
            .alert {{ background: #fef2f2; border-left: 4px solid #e74c3c; padding: 15px; margin: 20px 0; border-radius: 4px; }}
            .alert-title {{ font-weight: bold; color: #e74c3c; margin-bottom: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 每日执行摘要</h1>
            <div class="date">{summary['date']} {summary['weekday']}</div>
        </div>
        
        <div class="context">
            <span>🏢 工作日: {'是' if summary['is_workday'] else '否'}</span>
            <span>🇨🇳 A股交易: {'是' if summary['is_cn_trading'] else '否'}</span>
            <span>🇺🇸 美股交易: {'是' if summary['is_us_trading'] else '否'}</span>
            {f'<span>🎉 {summary["holiday"]}</span>' if summary['holiday'] else ''}
        </div>
        
        <div class="stats">
            <div class="stat success">
                <div class="value">{summary['success_count']}</div>
                <div class="label">成功</div>
            </div>
            <div class="stat failed">
                <div class="value">{summary['failed_count']}</div>
                <div class="label">失败</div>
            </div>
            <div class="stat pending">
                <div class="value">{summary['pending_count']}</div>
                <div class="label">未执行</div>
            </div>
            <div class="stat">
                <div class="value">{summary['skipped_count']}</div>
                <div class="label">跳过</div>
            </div>
        </div>
    """
    
    # 失败告警
    if summary['failed_modules']:
        html += """
        <div class="alert">
            <div class="alert-title">⚠️ 失败模块需要关注</div>
            <ul>
        """
        for f in summary['failed_modules']:
            html += f"<li><b>{f['module']}</b>: {f['error'] or '未知错误'}</li>"
        html += "</ul></div>"
    
    # 未执行告警
    if summary['pending_modules']:
        html += """
        <div class="alert">
            <div class="alert-title">⏳ 应运行但未执行的模块</div>
            <ul>
        """
        for m in summary['pending_modules']:
            html += f"<li><b>{m}</b></li>"
        html += "</ul></div>"
    
    # 详细表格
    html += """
        <h3>📋 执行详情</h3>
        <table>
            <tr>
                <th>模块</th>
                <th>计划时间</th>
                <th>状态</th>
                <th>执行时间</th>
            </tr>
    """
    
    for task in summary['all_tasks']:
        status = task['status']
        color = status_color(status)
        icon = status_icon(status)
        
        start_time = task.get('start_time', '-')
        if start_time and start_time != '-':
            try:
                start_time = datetime.fromisoformat(start_time).strftime('%H:%M:%S')
            except:
                pass
        
        should_run = '✓' if task['should_run'] else '-'
        
        html += f"""
            <tr>
                <td>{task['module']} {should_run}</td>
                <td>{task['scheduled_time']}</td>
                <td><span class="status-badge" style="background:{color}">{icon} {status}</span></td>
                <td>{start_time}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <p style="text-align:center; color:#999; font-size:12px; margin-top:20px;">
            Push Project Daily Summary | Generated at """ + datetime.now().strftime('%H:%M:%S') + """
        </p>
    </body>
    </html>
    """
    
    return html

def main():
    print("=" * 60)
    print("Daily Summary Report")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 获取调度器
    scheduler = get_scheduler()
    
    # 确保今天的计划已创建
    scheduler.plan_day()
    
    # 获取摘要
    summary = scheduler.get_daily_summary()
    
    # 打印摘要
    print(f"\n日期: {summary['date']} ({summary['weekday']})")
    print(f"工作日: {summary['is_workday']}, A股交易: {summary['is_cn_trading']}, 美股交易: {summary['is_us_trading']}")
    print(f"计划: {summary['total_planned']}, 成功: {summary['success_count']}, 失败: {summary['failed_count']}, 未执行: {summary['pending_count']}")
    
    if summary['failed_modules']:
        print("\n❌ 失败模块:")
        for f in summary['failed_modules']:
            print(f"  - {f['module']}: {f['error']}")
    
    if summary['pending_modules']:
        print("\n⏳ 未执行模块:")
        for m in summary['pending_modules']:
            print(f"  - {m}")
    
    # 生成 HTML
    html_content = generate_summary_html(summary)
    
    # 构建消息标题
    status_emoji = "✅" if summary['failed_count'] == 0 and summary['pending_count'] == 0 else "⚠️"
    title = f"{status_emoji} 每日摘要 {summary['date']} | {summary['success_count']}成功 {summary['failed_count']}失败"
    
    # 推送
    try:
        channel = PushPlusChannel()
        message = Message(
            title=title,
            content=html_content,
            type=ContentType.HTML,
            tags=['daily', 'summary', 'monitor']
        )
        
        if channel.send(message):
            print("\n✅ 摘要已推送")
        else:
            print("\n❌ 推送失败")
    except Exception as e:
        print(f"\n❌ 推送错误: {e}")
    
    # 保存 HTML 到文件
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output', 'summary')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"daily_{summary['date']}.html")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"📄 摘要已保存: {output_path}")

if __name__ == "__main__":
    main()
