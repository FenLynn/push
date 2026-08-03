"""Canonical Finance series that are safe to expose and retain."""

ARCHIVE_CATALOG = {
    "population": {
        "label": "人口与城镇化", "source": "国家统计局年鉴/公报（DBnomics 镜像）", "frequency": "annual",
        "metrics": {
            "population": {"label": "年末总人口", "unit": "万人"},
            "urban_population": {"label": "城镇人口", "unit": "万人"},
            "urbanization_rate": {"label": "城镇化率", "unit": "%"},
        },
    },
    "demography": {
        "label": "人口自然变动", "source": "国家统计局年鉴/公报（DBnomics 镜像）", "frequency": "annual",
        "metrics": {
            "birth_rate": {"label": "人口出生率", "unit": "‰"},
            "death_rate": {"label": "人口死亡率", "unit": "‰"},
            "natural_growth_rate": {"label": "人口自然增长率", "unit": "‰"},
        },
    },
    "fertility": {
        "label": "育龄妇女与生育率", "source": "UN World Population Prospects 2024（OWID 标准化转发）", "frequency": "annual",
        "quality": "estimated",
        "metrics": {
            "women_15_49": {"label": "15-49岁育龄妇女", "unit": "万人"},
            "women_20_34": {"label": "20-34岁妇女", "unit": "万人"},
            "total_fertility_rate": {"label": "总和生育率", "unit": "人/妇女"},
        },
    },
    "ageing": {
        "label": "人口老龄化", "source": "国家统计局年鉴/公报（DBnomics 镜像）", "frequency": "annual",
        "metrics": {
            "age_65_share": {"label": "65岁及以上人口占比", "unit": "%"},
            "gross_dependency_ratio": {"label": "总抚养比", "unit": "%"},
            "old_dependency_ratio": {"label": "老年抚养比", "unit": "%"},
        },
    },
    "marriage": {
        "label": "婚育登记", "source": "国家统计局/民政部（DBnomics 镜像）", "frequency": "annual",
        "metrics": {
            "marriages": {"label": "内地结婚登记", "unit": "万对"},
            "first_marriages": {"label": "初婚登记人数", "unit": "万人"},
            "divorces": {"label": "离婚登记", "unit": "万对"},
        },
    },
    "unemployment": {
        "label": "城镇调查失业率", "source": "国家统计局（DBnomics 镜像）", "frequency": "monthly",
        "metrics": {
            "urban_rate": {"label": "全国城镇调查失业率", "unit": "%"},
            "major_city_rate": {"label": "31个大城市调查失业率", "unit": "%"},
            "youth_rate": {"label": "16-24岁失业率（不含在校生）", "unit": "%"},
            "age_25_29_rate": {"label": "25-29岁失业率（不含在校生）", "unit": "%"},
            "age_30_59_rate": {"label": "30-59岁失业率（不含在校生）", "unit": "%"},
        },
    },
    "labour": {
        "label": "劳动供给", "source": "国家统计局（DBnomics 镜像）", "frequency": "annual",
        "metrics": {
            "active_population": {"label": "经济活动人口", "unit": "万人"},
            "registered_unemployed": {"label": "城镇登记失业人数", "unit": "万人"},
        },
    },
    "fiscal": {
        "label": "国家财政收支", "source": "国家统计局/财政部（DBnomics 镜像）", "frequency": "annual",
        "metrics": {
            "revenue": {"label": "全国财政收入", "unit": "亿元"},
            "expenditure": {"label": "全国财政支出", "unit": "亿元"},
            "revenue_growth": {"label": "财政收入增速", "unit": "%"},
            "expenditure_growth": {"label": "财政支出增速", "unit": "%"},
        },
    },
    "fiscalmonthly": {
        "label": "月度累计财政收支", "source": "国家统计局/财政部（DBnomics 镜像）", "frequency": "monthly",
        "metrics": {
            "revenue": {"label": "累计财政收入", "unit": "亿元"},
            "expenditure": {"label": "累计财政支出", "unit": "亿元"},
            "revenue_growth": {"label": "累计收入增速", "unit": "%"},
            "expenditure_growth": {"label": "累计支出增速", "unit": "%"},
        },
    },
    "taxstructure": {
        "label": "税收结构", "source": "国家统计局/财政部（DBnomics 镜像）", "frequency": "annual",
        "metrics": {
            "tax_revenue": {"label": "税收收入", "unit": "亿元"},
            "vat_share": {"label": "国内增值税占比", "unit": "%"},
            "consumption_tax_share": {"label": "国内消费税占比", "unit": "%"},
            "personal_tax_share": {"label": "个人所得税占比", "unit": "%"},
            "corporate_tax_share": {"label": "企业所得税占比", "unit": "%"},
        },
    },
    "governmentdebt": {
        "label": "广义政府杠杆率", "source": "国际清算银行 BIS 官方 SDMX API", "frequency": "quarterly",
        "metrics": {
            "government_debt_ratio": {"label": "广义政府债务/GDP", "unit": "%"},
        },
    },
    "cpi": {
        "label": "居民消费价格", "source": "AkShare/NBS", "frequency": "monthly",
        "metrics": {
            "cpi_y": {"label": "CPI 同比", "unit": "%"},
            "cpi_m": {"label": "CPI 环比", "unit": "%"},
        },
    },
    "ppi": {
        "label": "工业生产者价格", "source": "AkShare/NBS", "frequency": "monthly",
        "metrics": {
            "ppi_growth": {"label": "PPI 同比", "unit": "%"},
            "ppi_index_yoy": {"label": "PPI 同比指数", "unit": "index"},
        },
    },
    "scissorsgap": {
        "label": "CPI-PPI 同比增速差", "source": "Derived from AkShare/NBS", "frequency": "monthly", "quality": "derived",
        "metrics": {
            "cpi": {"label": "CPI 同比", "unit": "%"},
            "ppi": {"label": "PPI 同比", "unit": "%"},
            "gap": {"label": "CPI-PPI 同比增速差", "unit": "百分点"},
        },
    },
    "pmi": {
        "label": "采购经理指数", "source": "AkShare/NBS", "frequency": "monthly",
        "metrics": {
            "manufacture": {"label": "制造业 PMI", "unit": "index"},
            "non_manufacture": {"label": "非制造业 PMI", "unit": "index"},
        },
    },
    "gdp": {
        "label": "国内生产总值", "source": "AkShare/NBS", "frequency": "quarterly",
        "metrics": {
            "quarter_yoy": {"label": "GDP 单季度同比", "unit": "%"},
            "gdp_single": {"label": "GDP 当季值", "unit": "亿元"},
            "gdp_growth": {"label": "GDP 同比增速", "unit": "%"},
            "gdp_cumulative": {"label": "GDP 累计值", "unit": "亿元"},
        },
    },
    "m2": {
        "label": "货币供应量", "source": "AkShare/PBOC", "frequency": "monthly",
        "metrics": {
            "m2": {"label": "M2 余额", "unit": "亿元"},
            "m2_growth": {"label": "M2 同比增速", "unit": "%"},
        },
    },
    "m1m2gap": {
        "label": "M1-M2 同比增速差", "source": "Derived from AkShare/PBOC", "frequency": "monthly", "quality": "derived",
        "metrics": {
            "m1_growth": {"label": "M1 同比", "unit": "%"},
            "m2_growth": {"label": "M2 同比", "unit": "%"},
            "gap": {"label": "M1-M2 同比增速差", "unit": "百分点"},
        },
    },
    "socialfinance": {
        "label": "社会融资规模增量", "source": "AkShare/PBOC", "frequency": "monthly", "quality": "aggregated",
        "metrics": {
            "social_finance_increment": {"label": "社融增量", "unit": "亿元"},
            "rmb_loan_increment": {"label": "人民币贷款增量", "unit": "亿元"},
        },
    },
    "lpr": {
        "label": "贷款市场报价利率", "source": "AkShare/PBOC", "frequency": "monthly",
        "replace_observations": True,
        "metrics": {
            "lpr1y": {"label": "LPR 1年期", "unit": "%"},
            "lpr5y": {"label": "LPR 5年期以上", "unit": "%"},
            "lpr1y_unchanged_months": {"label": "LPR 1年期现值持续", "unit": "个月"},
            "lpr5y_unchanged_months": {"label": "LPR 5年期现值持续", "unit": "个月"},
            "unchanged_months": {"label": "当前报价持续", "unit": "个月"},
        },
    },
    "shibor": {
        "label": "上海银行间同业拆放利率", "source": "AkShare/CFETS", "frequency": "daily",
        "metrics": {
            "ON": {"label": "SHIBOR 隔夜", "unit": "%"},
            "3M": {"label": "SHIBOR 3个月", "unit": "%"},
            "1Y": {"label": "SHIBOR 1年", "unit": "%"},
        },
    },
    "bond": {
        "label": "中国国债收益率", "source": "AkShare/ChinaBond", "frequency": "daily",
        "metrics": {
            "y10": {"label": "中国国债 10年", "unit": "%"},
            "y2": {"label": "中国国债 2年", "unit": "%"},
            "spread": {"label": "国债期限利差", "unit": "bp"},
        },
    },
    "forex": {
        "label": "人民币汇率中间价", "source": "AkShare/SAFE", "frequency": "daily",
        "metrics": {
            "USD": {"label": "美元兑人民币", "unit": "CNY", "scale": 0.01},
            "EUR": {"label": "欧元兑人民币", "unit": "CNY", "scale": 0.01},
            "GBP": {"label": "英镑兑人民币", "unit": "CNY", "scale": 0.01},
            "JPY": {"label": "100日元兑人民币", "unit": "CNY"},
        },
    },
    "trade": {
        "label": "货物进出口", "source": "AkShare/Eastmoney/GACC", "frequency": "monthly", "quality": "aggregated",
        "metrics": {
            "export_yoy": {"label": "出口同比", "unit": "%"},
            "import_yoy": {"label": "进口同比", "unit": "%"},
            "trade_balance": {"label": "贸易差额", "unit": "亿美元"},
            "export_amount": {"label": "出口额", "unit": "亿美元"},
            "import_amount": {"label": "进口额", "unit": "亿美元"},
        },
    },
    "electricity": {
        "label": "全社会用电量", "source": "AkShare/Sina/NEA", "frequency": "monthly", "quality": "aggregated",
        "metrics": {
            "cumulative": {"label": "全社会累计用电量", "unit": "亿千瓦时"},
            "electricity_monthly": {"label": "当月用电量", "unit": "亿千瓦时"},
            "electricity_cumulative_yoy": {"label": "累计用电同比", "unit": "%"},
        },
    },
    "margin": {
        "label": "沪深融资融券", "source": "AkShare/SSE/SZSE", "frequency": "daily", "quality": "aggregated",
        "metrics": {
            "margin_balance": {"label": "融资余额", "unit": "亿元"},
            "margin_buy": {"label": "融资买入额", "unit": "亿元"},
            "sh_close": {"label": "上证指数收盘", "unit": "点"},
        },
    },
    "marketpe": {
        "label": "上证平均市盈率", "source": "AkShare/Legu", "frequency": "daily", "quality": "aggregated",
        "metrics": {
            "pe": {"label": "上证平均市盈率", "unit": "倍"},
            "sh_close": {"label": "上证指数收盘", "unit": "点"},
        },
    },
    "marketreview": {
        "label": "市场中周期复盘", "source": "Legulegu/ChinaBond/NBS/Eastmoney/SWS", "frequency": "daily", "quality": "aggregated",
        "metrics": {
            "csi300_close": {"label": "沪深300指数", "unit": "点"},
            "weighted_pe": {"label": "沪深300滚动市盈率", "unit": "倍"},
            "median_pe": {"label": "沪深300滚动市盈率中位数", "unit": "倍"},
            "bond_10y": {"label": "中国十年期国债收益率", "unit": "%"},
            "equity_yield_spread": {"label": "估值收益率减十年国债", "unit": "百分点"},
            "total_market_cap": {"label": "沪深市场总市值", "unit": "亿元"},
            "monthly_turnover": {"label": "沪深市场月成交额", "unit": "亿元"},
            "crowding_ratio": {"label": "月成交额占总市值", "unit": "%"},
            "gdp_ttm": {"label": "GDP滚动四季度", "unit": "亿元"},
            "buffett_ratio": {"label": "巴菲特指标", "unit": "%"},
            "margin_balance": {"label": "融资余额月末值", "unit": "亿元"},
            "margin_leverage": {"label": "融资余额占总市值", "unit": "%"},
            "industry_801010": {"label": "农林牧渔近一年涨跌幅", "unit": "%"},
            "industry_801030": {"label": "基础化工近一年涨跌幅", "unit": "%"},
            "industry_801040": {"label": "钢铁近一年涨跌幅", "unit": "%"},
            "industry_801050": {"label": "有色金属近一年涨跌幅", "unit": "%"},
            "industry_801080": {"label": "电子近一年涨跌幅", "unit": "%"},
            "industry_801110": {"label": "家用电器近一年涨跌幅", "unit": "%"},
            "industry_801120": {"label": "食品饮料近一年涨跌幅", "unit": "%"},
            "industry_801130": {"label": "纺织服饰近一年涨跌幅", "unit": "%"},
            "industry_801140": {"label": "轻工制造近一年涨跌幅", "unit": "%"},
            "industry_801150": {"label": "医药生物近一年涨跌幅", "unit": "%"},
            "industry_801160": {"label": "公用事业近一年涨跌幅", "unit": "%"},
            "industry_801170": {"label": "交通运输近一年涨跌幅", "unit": "%"},
            "industry_801180": {"label": "房地产近一年涨跌幅", "unit": "%"},
            "industry_801200": {"label": "商贸零售近一年涨跌幅", "unit": "%"},
            "industry_801210": {"label": "社会服务近一年涨跌幅", "unit": "%"},
            "industry_801230": {"label": "综合近一年涨跌幅", "unit": "%"},
            "industry_801710": {"label": "建筑材料近一年涨跌幅", "unit": "%"},
            "industry_801720": {"label": "建筑装饰近一年涨跌幅", "unit": "%"},
            "industry_801730": {"label": "电力设备近一年涨跌幅", "unit": "%"},
            "industry_801740": {"label": "国防军工近一年涨跌幅", "unit": "%"},
            "industry_801750": {"label": "计算机近一年涨跌幅", "unit": "%"},
            "industry_801760": {"label": "传媒近一年涨跌幅", "unit": "%"},
            "industry_801770": {"label": "通信近一年涨跌幅", "unit": "%"},
            "industry_801780": {"label": "银行近一年涨跌幅", "unit": "%"},
            "industry_801790": {"label": "非银金融近一年涨跌幅", "unit": "%"},
            "industry_801880": {"label": "汽车近一年涨跌幅", "unit": "%"},
            "industry_801890": {"label": "机械设备近一年涨跌幅", "unit": "%"},
            "industry_801950": {"label": "煤炭近一年涨跌幅", "unit": "%"},
            "industry_801960": {"label": "石油石化近一年涨跌幅", "unit": "%"},
            "industry_801970": {"label": "环保近一年涨跌幅", "unit": "%"},
            "industry_801980": {"label": "美容护理近一年涨跌幅", "unit": "%"},
        },
    },
    "crossborder": {
        "label": "中美十年期国债利差", "source": "Derived from AkShare/ChinaBond/US Treasury", "frequency": "daily", "quality": "derived",
        "metrics": {
            "cn_10y": {"label": "中国国债十年期", "unit": "%"},
            "us_10y": {"label": "美国国债十年期", "unit": "%"},
            "spread": {"label": "美债减中债利差", "unit": "百分点"},
        },
    },
    "insurance": {
        "label": "原保险保费收入", "source": "AkShare/Eastmoney/NFRA", "frequency": "monthly", "quality": "aggregated",
        "metrics": {
            "premium_monthly": {"label": "当月原保险保费", "unit": "亿元"},
            "premium_cumulative": {"label": "累计原保险保费", "unit": "亿元"},
            "premium_cumulative_yoy": {"label": "累计保费同比", "unit": "%"},
        },
    },
    "nevsale": {
        "label": "新能源乘用车零售", "source": "CPCA", "frequency": "monthly", "quality": "industry",
        "metrics": {
            "nev_retail_sales": {"label": "新能源乘用车零售销量", "unit": "万辆"},
            "nev_retail_share": {"label": "新能源零售渗透率", "unit": "%"},
            "nev_retail_yoy": {"label": "新能源零售同比", "unit": "%"},
        },
    },
    "realestate": {
        "label": "70城住宅价格景气", "source": "NBS/Eastmoney", "frequency": "monthly",
        "quality": "aggregated",
        "metrics": {
            "new_house_yoy": {"label": "70城新房同比中位数", "unit": "%"},
            "second_house_yoy": {"label": "70城二手房同比中位数", "unit": "%"},
            "new_house_rise_share": {"label": "新房环比上涨城市占比", "unit": "%"},
            "second_house_rise_share": {"label": "二手房环比上涨城市占比", "unit": "%"},
        },
    },
    "commodity": {
        "label": "COMEX 黄金", "source": "AkShare/Sina/COMEX", "frequency": "daily", "quality": "market",
        "metrics": {"close": {"label": "COMEX 黄金收盘价", "unit": "美元/盎司"}},
    },
    "sox": {
        "label": "费城半导体指数", "source": "AkShare/Sina", "frequency": "daily", "quality": "market",
        "metrics": {"close": {"label": "费城半导体指数", "unit": "点"}},
    },
    "sugar": {
        "label": "中国食糖综合价格", "source": "AkShare/沐甜科技", "frequency": "daily", "quality": "industry",
        "metrics": {
            "price": {"label": "食糖综合价格", "unit": "元/吨"},
            "spot_price": {"label": "食糖现货价格", "unit": "元/吨"},
        },
    },
    "commodityindex": {
        "label": "中国大宗商品价格指数", "source": "AkShare/Eastmoney", "frequency": "daily", "quality": "aggregated",
        "metrics": {"index": {"label": "大宗商品价格指数", "unit": "点"}},
    },
    "energyindex": {
        "label": "中国能源价格指数", "source": "AkShare/Eastmoney", "frequency": "daily", "quality": "aggregated",
        "metrics": {"index": {"label": "能源价格指数", "unit": "点"}},
    },
    "pig": {
        "label": "生猪市场价格", "source": "AkShare/搜猪/行情宝", "frequency": "daily", "quality": "industry",
        "metrics": {
            "daily_price": {"label": "全国瘦肉型生猪日价", "unit": "元/公斤"},
            "futures_price": {"label": "大商所生猪主连收盘", "unit": "元/公斤"},
            "index": {"label": "生猪价格指数", "unit": "点"},
            "transaction_price": {"label": "生猪成交均价", "unit": "元/公斤"},
        },
    },
    "oil": {
        "label": "国内汽柴油基准价", "source": "AkShare/Eastmoney", "frequency": "event", "quality": "aggregated",
        "metrics": {
            "gasoline": {"label": "汽油基准价", "unit": "元/吨"},
            "diesel": {"label": "柴油基准价", "unit": "元/吨"},
            "gasoline_liter_est": {"label": "汽油折算估值", "unit": "元/L"},
            "diesel_liter_est": {"label": "柴油折算估值", "unit": "元/L"},
            "days_current": {"label": "本轮价格持续", "unit": "天"},
        },
    },
    "internationalrate": {
        "label": "主要央行政策利率", "source": "Federal Reserve/ECB/BOJ/FRED/PBOC", "frequency": "event", "quality": "official",
        "replace_observations": True,
        "metrics": {
            "usa": {"label": "美联储目标区间上限", "unit": "%"},
            "eur": {"label": "欧洲央行存款便利利率", "unit": "%"},
            "jpy": {"label": "日本隔夜拆借利率", "unit": "%"},
            "cn": {"label": "中国1年期LPR参考", "unit": "%"},
        },
    },
    "news": {
        "label": "新闻联播条目数", "source": "AkShare/CCTV", "frequency": "daily", "quality": "official",
        "metrics": {"news_count": {"label": "当期新闻条目", "unit": "条"}},
    },
    "realinterestrate": {
        "label": "中国事后实际利率代理", "source": "Derived from AkShare/ChinaBond/NBS", "frequency": "monthly", "quality": "derived",
        "metrics": {
            "real": {"label": "实际利率代理", "unit": "%"},
            "nominal": {"label": "十年国债月均收益率", "unit": "%"},
            "cpi": {"label": "CPI 同比", "unit": "%"},
        },
    },
}
