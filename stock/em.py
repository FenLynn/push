import requests 
from bs4 import BeautifulSoup 
import pandas as pd 
import jieba 
from snownlp import SnowNLP 
import matplotlib.pyplot  as plt 
from tqdm import tqdm 
 
# 配置参数 
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}
 
def fetch_guba_posts(stock_code, pages=5):
    """爬取东方财富股吧帖子"""
    base_url = f'http://guba.eastmoney.com/list,{stock_code}_' 
    posts = []
    
    for page in tqdm(range(1, pages+1)):
        url = base_url + f'{page}.html'
        try:
            response = requests.get(url,  headers=headers, timeout=10)
            soup = BeautifulSoup(response.text,  'html.parser') 
            articles = soup.select('.articleh') 
            
            for art in articles:
                try:
                    time = art.select('.l5')[0]().text.strip() 
                    title = art.select('a')[0]() 
                    posts.append({'time':  time, 'content': title})
                except:
                    continue 
        except Exception as e:
            print(f"第{page}页抓取失败：{str(e)}")
    
    return pd.DataFrame(posts)
 
def sentiment_analysis(df):
    """情感分析处理"""
    # 数据清洗 
    df = df.drop_duplicates('content') 
    df['content'] = df['content'].str.replace(r'[^\u4e00-\u9fa5]',  '', regex=True)
    
    # 情感计算 
    df['sentiment'] = df['content'].apply(lambda x: SnowNLP(x).sentiments)
    df['emotion'] = df['sentiment'].apply(lambda x: '乐观' if x > 0.6 else '中性' if x > 0.4 else '悲观')
    
    return df 
 
# 执行爬取与分析（以贵州茅台为例）
stock_code = '600519'  # 股票代码 
df = fetch_guba_posts(stock_code, pages=10)
analyzed_df = sentiment_analysis(df)
 
# 可视化结果 
plt.figure(figsize=(15,5)) 
 
# 情绪分布直方图
plt.subplot(121) 
analyzed_df['sentiment'].hist(bins=20)
plt.title(' 情感值分布直方图')
plt.xlabel(' 情感值')
plt.ylabel(' 频次')
 
# 情绪时间走势 
plt.subplot(122) 
analyzed_df.groupby('time')['sentiment'].mean().plot() 
plt.title(' 情绪值时间走势')
plt.xticks(rotation=45) 
plt.tight_layout() 
plt.show() 
 
# 输出统计结果 
print(f"情绪分布统计:\n{analyzed_df['emotion'].value_counts()}")
print(f"\n典型乐观语句示例:\n{analyzed_df[analyzed_df['sentiment']>0.8].sample(3)['content'].values}")
print(f"\n典型悲观语句示例:\n{analyzed_df[analyzed_df['sentiment']<0.3].sample(3)['content'].values}")