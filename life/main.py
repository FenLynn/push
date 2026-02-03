import sys 
sys.path.append("..") 
from cloud import *
from cloud.utils.lib import *

from io import BytesIO
import cv2
###########################################################################################################
#root_path = os.path.abspath(os.path.dirname(__file__))
#package_name=__package__

pic_type='.jpg'
pic_path='./pic/'


###########################################################################################################

def create_html(filename='./life.html',strs=''):
    print ('2. Generating html ... ')
    with open(filename,'w') as f:
        f.write(strs)
    f.close
    return filename

def pushplus(topic='me'):
    print ('Pushing html by pushplus to Wechat ... ')
    response=send_message(key=topic,_itype='file',_str="life.html",_title='影视数据({})'.format(time.strftime('%m-%d', time.localtime(time.time()))),_template='html',_send_type='post')
    #response=send_message(key=topic,_itype='file',_str="./test.md",_title='ETF({})'.format(time.strftime('%Y-%m-%d', time.localtime(time.time()))),_template='markdown',_send_type='post')
    print ('Sent by pushplus!')         
##############################################################################################################
def get_movie():
    df = ak.movie_boxoffice_realtime()
    df['累计票房']=round(df['累计票房']/10000.,2)
    #strs=df.set_table_attributes('class="table-style"').to_html(index=False,justify='center',columns=['影片名称','实时票房','上映天数','累计票房','票房占比'],col_space='75px')
    strs=df.to_html(index=False,justify='justify',columns=['影片名称','实时票房','票房占比','上映天数','累计票房'],col_space='80px')
    #df['累计票房']=round(df['累计票房']/10000.,2)
    #strs=df[['影片名称','实时票房','票房占比','上映天数','累计票房']].to_markdown(index=False)
    #strs=df.to_html(index=False,justify='center')
    #strs=strs.replace('<tr>', '<tr align="center">')
    # print (strs)
    strs = re.sub(r'(\d+)px;">影片名称', '140px;">影片名称', strs)
    strs = re.sub(r'(\d+)px;">实时票房', '70px;">实时票房', strs)
    strs = re.sub(r'(\d+)px;">票房占比', '60px;">票房占比', strs)
    strs = re.sub(r'(\d+)px;">上映天数', '60px;">上映天数', strs)
    strs = re.sub(r'(\d+)px;">累计票房', '60px;">累计票房', strs)

    return strs

def get_movie_year():
    df = ak.movie_boxoffice_yearly(get_time_ymd_str())
    df['总票房']=round(df['总票房']/10000.,2)
    #strs=df.set_table_attributes('class="table-style"').to_html(index=False,justify='center',columns=['影片名称','实时票房','上映天数','累计票房','票房占比'],col_space='75px')排序           影片名称   类型      总票房  平均票价  场均人次    国家及地区        上映日期
    strs=df.to_html(index=False,justify='justify',columns=['影片名称','总票房','类型','场均人次','上映日期'],col_space='80px')
    #df['累计票房']=round(df['累计票房']/10000.,2)
    #strs=df[['影片名称','实时票房','票房占比','上映天数','累计票房']].to_markdown(index=False)
    #strs=df.to_html(index=False,justify='center')
    #strs=strs.replace('<tr>', '<tr align="center">')
    strs = re.sub(r'(\d+)px;">影片名称', '140px;">影片名称', strs)
    strs = re.sub(r'(\d+)px;">总票房', '50px;">总票房', strs)
    strs = re.sub(r'(\d+)px;">类型', '50px;">类型', strs)
    strs = re.sub(r'(\d+)px;">场均人次', '60px;">场均人次', strs)
    strs = re.sub(r'(\d+)px;">上映日期', '80px;">上映日期', strs)

    return strs




def get_tv():
    df = ak.video_tv()
    df = df.sort_values(by='用户热度',ascending=False)
    strs=df.to_html(index=False,justify='justify',columns=['名称','类型','播映指数','用户热度','好评度'],col_space='80px')
    #strs=df.to_html(index=False,justify='center',columns=['名称','播映指数','用户热度','好评度'])
    strs = re.sub(r'(\d+)px;">名称', '140px;">名称', strs)
    strs = re.sub(r'(\d+)px;">类型', '80px;">类型', strs)
    strs = re.sub(r'(\d+)px;">播映指数', '60px;">播映指数', strs)
    strs = re.sub(r'(\d+)px;">用户热度', '60px;">用户热度', strs)
    strs = re.sub(r'(\d+)px;">好评度', '50px;">好评度', strs)
    return strs

def get_show():
    df = ak.video_variety_show()
    df = df.sort_values(by='用户热度',ascending=False)
    strs=df.to_html(index=False,justify='justify',columns=['名称','类型','播映指数','用户热度','好评度'],col_space='80px')
    strs = re.sub(r'(\d+)px;">名称', '120px;">名称', strs)
    strs = re.sub(r'(\d+)px;">类型', '90px;">类型', strs)
    strs = re.sub(r'(\d+)px;">播映指数', '60px;">播映指数', strs)
    strs = re.sub(r'(\d+)px;">用户热度', '60px;">用户热度', strs)
    strs = re.sub(r'(\d+)px;">好评度', '50px;">好评度', strs)
    return strs


def get_news():
    url='https://v.api.aa1.cn/api/60s-v3/?cc=%E5%9B%BD%E5%86%85%E8%A6%81%E9%97%BB' #API简介：官方新闻第三版，展示最新新闻，每天24期次，欢迎使用
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    image_data=response.content
    pic_path='./pic/news.jpg'
    with open(pic_path,'wb') as f:
        f.write(image_data)
    #pic_size = pic_compress(pic_path, pic_path, target_size=150)
    #print("图片压缩后的大小为(KB)：", pic_size)
    pic_url=uploadPic(pic_path)
    return pic_url
    pass


def pic_compress(pic_path, out_path, target_size=199, quality=99, step=2, pic_type='.jpg'):
    # 读取图片bytes
    with open(pic_path, 'rb') as f:
        pic_byte = f.read()
    img_np = np.frombuffer(pic_byte, np.uint8)
    img_cv = cv2.imdecode(img_np, cv2.IMREAD_ANYCOLOR)
    current_size = len(pic_byte) / 1024
    print("图片压缩前的大小为(KB)：", current_size)
    while current_size > target_size:
        pic_byte = cv2.imencode(pic_type, img_cv, [int(cv2.IMWRITE_JPEG_QUALITY), quality])[1]
        if quality - step < 0:
            break
        quality -= step
        current_size = len(pic_byte) / 1024
    # 保存图片
    with open(out_path, 'wb') as f:
        f.write(BytesIO(pic_byte).getvalue())
    return len(pic_byte) / 1024



def get_data():
    tempStr='🕔更新时间:{0} \n'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
    tempStr+='<head><style>table th {font-weight: bold; text-align: center !important; background: rgba(158,188,226,0.2); white-space: wrap;}table tbody tr:nth-child(2n) { background-color: #f2f2f2;}table{text-align: center;font-family: Arial, sans-serif; font-size: 13px;}</style><meta charset="utf-8"><style>html{font-family:sans-serif;}table{border-collapse:collapse;cellspacing="5"}td,th {border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}</style></head>'
    #tempStr+='<a><img src="{}" alt="news"></a></br>'.format(_pic_url)
    #tempStr+='☀️ 新闻播报:</br> '
    #tempStr+='<a><img src="{}" alt="news"></a></br>'.format(get_news_url(out_path='./pic/news.jpg'))
    tempStr+='&#9210; <b>电影票房实时数据</b></br> '
    tempStr+=get_movie()
    tempStr+='&#9210; <b>今年累计票房</b></br>'
    tempStr+=get_movie_year()
    tempStr+='&#9210; <b>电视剧集</b></br>'
    tempStr+=get_tv()
    tempStr+='&#9210; <b>综艺节目</b></br>'
    tempStr+=get_show()
    return tempStr


def create_md(filename='./life.md',strs=''):
    print ('2. Generating html ... ')
    with open(filename,'w') as f:
        f.write(strs)
    f.close
    return filename


##############################################################################################################
@timer_decorator 
def main(topic):           
    ############# topic #######################
    print ('topic: {}'.format(topic))
    print ('1. Fetching data  ... ')
    #pic_url=get_news()
    strs=get_data()
    create_html('./life.html',strs)
    pushplus(topic)
    print('finished\n')

def only_send(topic):
    response=bb.send_message(key=topic,_itype='file',_str="./life.html",_title='test {}'.format(time.strftime('%m-%d', time.localtime(time.time()))),_template='html',_send_type='post')


def test():
    s=get_movie()
    create_html('./life.md',s)




if __name__ == '__main__':
    if len(sys.argv) == 1:
        main('me')
        #test()
        #only_send('me')
        #load_generate_html('me')
    else:
        para_argv=sys.argv[1][1:]
        main(para_argv)

