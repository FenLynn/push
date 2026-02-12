import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, WeekdayLocator, DayLocator, MONDAY,YEARLY,MonthLocator, YearLocator
import sys
import os
from string import Template
import csv
from datetime import datetime,date,timedelta
import time
from chinese_calendar import is_workday, is_holiday, is_in_lieu, get_holiday_detail
import pandas as pd
import akshare as ak
import numpy as np
import requests     # 第三方 安装
import jieba
import wordcloud
from PIL import Image
import socket
import re
from tqdm import tqdm
import random
from bs4 import BeautifulSoup
from zhdate import ZhDate
import json
from urllib.parse import quote
import urllib.parse
from lxml import etree
import random
from io import BytesIO
import cv2
import base64

### paper module
from datetime import datetime, timezone, timedelta
from ttrss.client import TTRClient



##### matplotlib
#### matplotlib config
plt.rcParams.update(plt.rcParamsDefault)
#plt.rc("font",family='MicroSoft YaHei')
plt.rcParams['xtick.direction'] = 'in'
plt.rcParams['ytick.direction'] = 'in'
plt.rcParams['axes.grid.which'] = 'both'
plt.rcParams['grid.color'] = 'grey'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.3
plt.rcParams['font.family']=['sans-serif'] #用来正常显示中文标签
plt.rcParams['xtick.direction'] = 'in'
plt.rcParams['ytick.direction'] = 'in'
plt.subplots_adjust(hspace=0.1,wspace=0.1)
plt.gcf().autofmt_xdate()
plt.rcParams['font.sans-serif']=['Microsoft YaHei']
mycolors=['lightcoral','dodgerblue','teal','plum','darkorange','lightskyblue','mediumturquoise']


