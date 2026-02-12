
import inspect 
import os
import jieba
import wordcloud
import numpy as np
from PIL import Image
from core.config import config
from core.utils.lib import *

# Define paths based on Core Config
root_path = config.root_path
font_path = os.path.join(root_path, 'utils', 'msyh.ttc')
# Note: cloud/utils/china.jpg and cloud/utils/table.css were moved?
# Wait, I only moved default.ini. I need to move other assets too.
# Assuming assets will be moved to core/utils/assets or root/utils?
# cloud/tool.py used root_path+'/utils/china.jpg'.
# So I should move cloud/utils content to root/utils/ or core/utils/?
# I'll tentatively point to core/utils/ for now and ensure files are moved there.
# But cloud/tool.py said `root_path+'/utils/china.jpg'`. root_path was `cloud/`.
# So it was `cloud/utils/china.jpg`.
# If I move to `core/utils/`, ConfigLoader.root_path is `project_root` (nfs/python/push).
# I should place assets in `project_root/assets/` or keep in `core/utils/`?
# Let's keep existing structure where possible but cleaning up.
# I'll move assets to `core/utils/` and update paths here.

css_file = 'table.css'

def print_line_number():
    current_frame = inspect.currentframe() 
    print(f"当前行号: {current_frame.f_lineno}")
 
def get_wordcloud(str_list='', pic_path='./wc.jpg', bkg_pic_path=None):
    if str_list == '':
        print ('str is necessary')
        return '' 
    
    # Default path handling
    if bkg_pic_path is None:
        # Fallback to china.jpg in core/utils directory
        bkg_pic_path = os.path.join(os.path.dirname(__file__), 'china.jpg')

    s=str_list
    mask = np.array(Image.open(bkg_pic_path))
    ls = jieba.lcut(s) 
    text = ' '.join(ls)
    
    _font_path = font_path
    if not os.path.exists(_font_path):
        # Try finding font in current dir or system
        _font_path = os.path.join(os.path.dirname(__file__), 'msyh.ttc')
        
    wc = wordcloud.WordCloud(font_path=_font_path,scale=1,
                              width = 1000,
                              height = 700,
                              background_color='white',
                              max_words=100,stopwords=s,mask=mask) 
    wc.generate(text) 
    wc.to_file(pic_path) 
 
def filter_wordcloud_stopword(s, stopword=[]):
    # stopword default was imported from config?
    # cloud/config.py defined stopword=['...']
    # I should pass it or define it here.
    for i in stopword:
        s=s.replace(i,'')
    return s
 
def get_css(cssfile=None):
    if cssfile is None:
         cssfile = os.path.join(os.path.dirname(__file__), css_file)
         
    with open(cssfile,  'r', encoding='utf-8') as src:
        content = src.read() 
    return content
