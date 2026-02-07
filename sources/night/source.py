"""
Night Source - 美股夜盘数据推送
整合原 night/main.py 功能：美股指数 + 美股自选股
"""
import sys, os, time
from string import Template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sources.base import BaseSource
from core import Message, ContentType

# 导入原有的 cloud 库
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from cloud import *
from cloud.utils.lib import *


class NightSource(BaseSource):
    """美股夜盘数据源"""
    
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        
        # 代理设置
        if is_use_proxy:
            use_proxy()
    
    def run(self) -> Message:
        """生成美股夜盘报告"""
        index_html = self._get_us_index()
        stock_html = self._get_us_stock()
        
        html_content = self._create_html(index_html, stock_html)
        title = f'夜盘股市({time.strftime("%m-%d", time.localtime())})'
        
        return Message(
            title=title,
            content=html_content,
            type=ContentType.HTML,
            tags=['night', 'us_market', self.topic]
        )
    
    def _get_growth_color(self, num):
        """根据涨跌幅返回颜色"""
        return "#3CB371" if num < 0 else "#CD5C5C" if num > 0 else "black"
    
    def _get_us_index(self):
        """获取美股指数"""
        try:
            df = ak.index_global_spot_em()
            df = df[df['代码'].isin(['BDI','VNINDEX','RTS','SENSEX','GDAXI','MCX','NDX','UDI','SX5E','FCHI','N225','SPX','DJIA'])].reset_index(drop=True)
        except Exception as e:
            print(f"[Night] Failed to load US index: {e}")
            return ""
        
        table_head = '<table><tr align=center><th style="min-width:20px">序</th><th style="min-width:150px">名称</th><th style="min-width:50px">涨跌幅</th><th style="min-width:50px">振幅</th><th style="min-width:110px">更新时间</th></tr>${CONTENT}</table>'
        bold_list = ['UDI', 'NDX', 'SPX', 'DJIA']
        
        rows = ""
        for i in df.index:
            time_str = datetime.strptime(df.loc[i, '最新行情时间'], "%Y-%m-%d %H:%M:%S").strftime("%m/%d %H:%M:%S")
            color = self._get_growth_color(df.loc[i, '涨跌幅'])
            
            if df.loc[i, '代码'] in bold_list:
                rows += f'<tr><td align="center"><b>{i+1}</b></td><td align="center"><b>{df.loc[i, "名称"]}</b></td><td><font color={color}><b>{df.loc[i, "涨跌幅"]}</b></font></td><td align="center"><b>{df.loc[i, "振幅"]}</b></td><td align="center"><b>{time_str}</b></td></tr>'
            else:
                rows += f'<tr><td align="center">{i+1}</td><td align="center">{df.loc[i, "名称"]}</td><td><font color={color}>{df.loc[i, "涨跌幅"]}</font></td><td align="center">{df.loc[i, "振幅"]}</td><td align="center">{time_str}</td></tr>'
        
        return Template(table_head).safe_substitute({'CONTENT': rows})
    
    def _get_us_stock(self):
        """获取美股自选股"""
        try:
            df = ak.stock_us_spot_em()
        except Exception as e:
            print(f"[Night] Failed to load US stocks: {e}")
            return ""
        
        df = df.sort_values(by='涨跌幅', ascending=False)
        
        us_stock_list = ['105.KHC','105.AAPL','105.MSFT','105.NVDA','105.AMZN','105.GOOG','105.META','106.TSM','105.TSLA','106.BRK_A','106.BABA','106.PDD','106.JD','106.BILI','106.ONC','106.EDU','106.BAC','106.KO','105.NFLX','106.AXP','106.GS','106.PFE','106.BLK','106.BA','106.LMT','105.AXP','106.OXY','106.MCO','106.CB']
        df = df[df['代码'].isin(us_stock_list)].reset_index(drop=True)
        df['成交额'] = df['成交额'].apply(lambda x: round(x / 100000000., 2))
        df['总市值'] = df['总市值'].apply(lambda x: int(x / 100000000))
        
        bold_list = ['105.AAPL', '105.NVDA', '105.TSLA', '106.BABA']
        table_head = '<table><tr align=center><th style="min-width:25px">序</th><th style="min-width:120px">名称</th><th style="min-width:55px">涨跌幅</th><th style="min-width:55px">成交额</th><th style="min-width:55px">市盈率</th><th style="min-width:60px">总市值</th></tr>${CONTENT}</table>'
        
        rows = ""
        for i in df.index:
            color = self._get_growth_color(df.loc[i, '涨跌幅'])
            
            if df.loc[i, '代码'] in bold_list:
                rows += f'<tr><td align="center"><b>{i+1}</b></td><td align="center"><b>{df.loc[i, "名称"]}</b></td><td><font color={color}><b>{df.loc[i, "涨跌幅"]}</b></font></td><td align="center"><b>{df.loc[i, "成交额"]}</b></td><td align="center"><b>{df.loc[i, "市盈率"]}</b></td><td align="center"><b>{df.loc[i, "总市值"]}</b></td></tr>'
            else:
                rows += f'<tr><td align="center">{i+1}</td><td align="center">{df.loc[i, "名称"]}</td><td><font color={color}>{df.loc[i, "涨跌幅"]}</font></td><td align="center">{df.loc[i, "成交额"]}</td><td align="center">{df.loc[i, "市盈率"]}</td><td align="center">{df.loc[i, "总市值"]}</td></tr>'
        
        return Template(table_head).safe_substitute({'CONTENT': rows})
    
    def _create_html(self, index_html, stock_html):
        """生成 HTML"""
        html_head = '<html><head><style>.grid-container {display: grid;grid-template-columns: repeat(2, 1fr); gap: 5px;}table th {font-weight: bold; text-align: center !important; background: rgba(158,188,226,0.2); white-space: wrap;}table tbody tr:nth-child(2n) { background-color: #f2f2f2;}table{text-align: center;font-family: Arial, sans-serif; font-size: 15px;}</style><meta charset="utf-8"><style>html{font-family:sans-serif;}table{border-collapse:collapse;}td,th {border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}</style></head><body>'
        
        content = html_head
        content += f'🕔更新时间:{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())} \n'
        
        if index_html:
            content += '📈 <font color= blue><b>夜盘指数</b></font>\n'
            content += index_html
            content += '<img src="https://image.sinajs.cn/newchart/usstock/min/IXIC.gif"/>'
        
        if stock_html:
            content += '\n📈 <font color= blue><b>夜盘股票</b></font>\n'
            content += stock_html
            content += '<div class="grid-container"><img src="https://image.sinajs.cn/newchart/usstock/min/TSLA.gif"/><img src="https://image.sinajs.cn/newchart/usstock/min/nvda.gif"/></div>'
            content += '<div class="grid-container"><img src="https://image.sinajs.cn/newchart/usstock/min/AAPL.gif"/><img src="https://image.sinajs.cn/newchart/usstock/min/BABA.gif"/></div>'
        
        content += '</body></html>'
        return content


if __name__ == '__main__':
    source = NightSource(topic='me')
    msg = source.run()
    print(f"Title: {msg.title}")
    print(f"Type: {msg.type}")
    print(f"Content length: {len(msg.content)} chars")
