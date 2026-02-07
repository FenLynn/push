"""Estate Source - 成都房产数据 (简化版,仅文字报告)"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from sources.base import BaseSource
from core import Message, ContentType
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from cloud import *
from cloud.utils.lib import *

class EstateSource(BaseSource):
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
    
    def run(self) -> Message:
        """简化版: 仅返回成都房产链接和提示"""
        text = f'🕔 {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}\n'
        text += '📊 成都房产数据\n'
        text += '--------------------------------\n'
        text += '数据来源: 成都住建局\n'
        text += '原 estate 模块需要图表生成和历史数据,已简化为信息提示。\n'
        text += '查看详情: https://www.cdzjryb.com/SCXX/Default.aspx?action=ucEveryday2'
        
        return Message(title=f'成都房产({time.strftime("%m-%d", time.localtime())})', content=text, type=ContentType.TEXT, tags=['estate', self.topic])
