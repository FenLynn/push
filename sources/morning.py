"""
Morning Source - 早报推送
简化版试点，展示新架构
"""
import sys
import os
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources.base import BaseSource
from core import Message, ContentType


class MorningSource(BaseSource):
    """早报数据源"""
    
    def run(self) -> Message:
        """
        生成早报内容
        
        Returns:
            Message: 早报消息
        """
        # 获取当前时间
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        weekday = now.strftime("%A")
        
        # 构建上下文
        context = {
            'date': date_str,
            'weekday': weekday,
            'greeting': self._get_greeting(now.hour),
            'weather': '☀️ 晴朗',  # 简化版，实际可调用天气 API
            'items': [
                {'icon': '📅', 'text': f'今天是 {now.strftime("%m月%d日")}'},
                {'icon': '⏰', 'text': '新的一天开始了！'},
            ]
        }
        
        # 渲染模板
        content = self.render_template('morning.html', context)
        
        return Message(
            title=f'早报 ({date_str})',
            content=content,
            type=ContentType.HTML,
            tags=['morning', 'daily']
        )
    
    def _get_greeting(self, hour: int) -> str:
        """根据时间生成问候语"""
        if hour < 6:
            return "凌晨好"
        elif hour < 12:
            return "早上好"
        elif hour < 18:
            return "下午好"
        else:
            return "晚上好"


if __name__ == '__main__':
    # 独立运行测试
    source = MorningSource()
    msg = source.run()
    print(f"Title: {msg.title}")
    print(f"Type: {msg.type}")
    print(f"Content:\n{msg.content}")
