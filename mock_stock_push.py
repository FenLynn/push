import sys
import os
import jinja2
import time
from cloud.net import send_message

def render_template(template_name, context):
    template_loader = jinja2.FileSystemLoader(searchpath="/nfs/python/push/templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template(template_name)
    return template.render(context)

def mock_run():
    print("Generating mock Stock report...")
    
    data = {
        'trade_status': True,
        'update_time': time.strftime("%Y-%m-%d %H:%M:%S"),
        'summary': {
            'total_money': '8543',
            'volume_ratio': '1.05',
            'up_sum': 3241,
            'down_sum': 1532,
            'long_10': 45,
            'short_10': 3,
            'mean': 0.45,
            'median': 0.32
        },
        'indexes': [
            {'name': '上证指数', 'close': 3452.12, 'growth_rate': 0.85, 'turnover_billion': 3542.12, 'url': '#'},
            {'name': '创业板指', 'close': 2345.67, 'growth_rate': -0.45, 'turnover_billion': 1853.3, 'url': '#'},
            {'name': '国证A指', 'close': 5678.90, 'growth_rate': 0.65, 'turnover_billion': 8900.0, 'url': '#'},
            {'name': '上证50', 'close': 2890.12, 'growth_rate': 1.23, 'turnover_billion': 1200.5, 'url': '#'},
            {'name': '沪深300', 'close': 4012.34, 'growth_rate': 0.98, 'turnover_billion': 2300.6, 'url': '#'}
        ],
        'sectors': {
            'leaders': [
                {'name': '半导体', 'change': 3.52},
                {'name': '新能源车', 'change': 2.85},
                {'name': '人工智能', 'change': 2.41},
                {'name': '军工', 'change': 1.95},
                {'name': '医药', 'change': 1.63}
            ],
            'losers': [
                {'name': '房地产', 'change': -1.25},
                {'name': '银行', 'change': -0.85},
                {'name': '煤炭', 'change': -0.63},
                {'name': '钢铁', 'change': -0.42},
                {'name': '石油', 'change': -0.21}
            ]
        },
        'stocks': [
            {'name': '隆基绿能', 'code': '601012', 'close': 45.60, 'growth_rate': -1.23, 'turnover_billion': 4.5, 'url': '#'},
            {'name': '贵州茅台', 'code': '600519', 'close': 1785.00, 'growth_rate': 0.45, 'turnover_billion': 45.2, 'url': '#'},
            {'name': '宁德时代', 'code': '300750', 'close': 235.60, 'growth_rate': 2.34, 'turnover_billion': 38.5, 'url': '#'},
        ],
        'etfs': [
             {'name': '光伏ETF', 'code': '515790', 'close': 0.890, 'growth_rate': -1.50, 'turnover_billion': 0.5, 'url': '#'},
             {'name': '芯片ETF', 'code': '159995', 'close': 1.230, 'growth_rate': 2.10, 'turnover_billion': 1.2, 'url': '#'},
             {'name': '中概互联网', 'code': '513050', 'close': 0.780, 'growth_rate': 3.50, 'turnover_billion': 2.5, 'url': '#'}
        ],
        'turnover_ranking': [
            {'name': '东方财富', 'close': 15.67, 'growth_rate': 5.67, 'turnover_billion': 105.2, 'url': '#'},
            {'name': '中信证券', 'close': 23.45, 'growth_rate': 2.34, 'turnover_billion': 89.5, 'url': '#'},
             {'name': '宁德时代', 'close': 235.60, 'growth_rate': 2.34, 'turnover_billion': 38.5, 'url': '#'},
             {'name': '贵州茅台', 'close': 1785.0, 'growth_rate': 0.45, 'turnover_billion': 45.2, 'url': '#'},
             {'name': '中科曙光', 'close': 45.67, 'growth_rate': 4.56, 'turnover_billion': 54.3, 'url': '#'}
        ],
        'hot_stocks': [
            {'name': 'N新股', 'close': 45.67, 'growth_rate': 156.7, 'turnover_billion': 12.3, 'url': '#'},
            {'name': '某连板股', 'close': 23.45, 'growth_rate': 10.02, 'turnover_billion': 8.9, 'url': '#'},
            {'name': '某热门股', 'close': 12.34, 'growth_rate': -9.98, 'turnover_billion': 23.4, 'url': '#'}
        ],
        'new_highs': [
             {'name': '长江电力', 'code': '600900', 'close': 25.67, 'growth_rate': 1.23, 'url': '#'},
             {'name': '紫金矿业', 'code': '601899', 'close': 15.43, 'growth_rate': 2.34, 'url': '#'}
        ]
    }
    
    html = render_template('stock.html', data)
    
    # Send Push
    title = f'自选股(UI V3)'
    send_message(key='me', _itype='str', _str=html, _title=title, _template='html', _send_type='post')
    print("Push sent via PushPlus (to me only)")

if __name__ == '__main__':
    mock_run()
