import inspect 
from .config import *
from .utils.lib import *
 
def print_line_number():
    current_frame = inspect.currentframe() 
    print(f"当前行号: {current_frame.f_lineno}")
 
def get_wordcloud(str_list='',pic_path='./'+'wc'+'.jpg',bkg_pic_path=root_path+'/utils/china.jpg'):
    if str_list == '':
        print ('str is necessary')
        return '' 
    s=str_list
    mask = np.array(Image.open(bkg_pic_path))
    ls = jieba.lcut(s) # 生成分词列表
    text = ' '.join(ls) # 连接成字符串    
    _font_path=font_path
    wc = wordcloud.WordCloud(font_path=_font_path,scale=1,
                              width = 1000,
                              height = 700,
                              background_color='white',
                              max_words=100,stopwords=s,mask=mask) # msyh.ttc电脑本地字体，写可以写成绝对路径
    wc.generate(text) # 加载词云文本
    wc.to_file(pic_path) # 保存词云文件
 
def filter_wordcloud_stopword(s,stopword=stopword):
    for i in stopword:
        s=s.replace(i,'')
    return s
 
def get_css(cssfile=root_path+'/utils/'+css_file):
    with open(cssfile,  'r', encoding='utf-8') as src:
        content = src.read() 
    return content
