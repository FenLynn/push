"""Canonical Finance series that are safe to expose and retain."""

ARCHIVE_CATALOG = {
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
        "metrics": {
            "lpr1y": {"label": "LPR 1年期", "unit": "%"},
            "lpr5y": {"label": "LPR 5年期以上", "unit": "%"},
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
            "electricity_monthly": {"label": "当月用电量", "unit": "亿千瓦时"},
            "electricity_cumulative_yoy": {"label": "累计用电同比", "unit": "%"},
        },
    },
    "margin": {
        "label": "沪深融资融券", "source": "AkShare/SSE/SZSE", "frequency": "daily", "quality": "aggregated",
        "metrics": {
            "margin_balance": {"label": "融资余额", "unit": "亿元"},
            "margin_buy": {"label": "融资买入额", "unit": "亿元"},
        },
    },
    "marketpe": {
        "label": "上证平均市盈率", "source": "AkShare/Legu", "frequency": "daily", "quality": "aggregated",
        "metrics": {"pe": {"label": "上证平均市盈率", "unit": "倍"}},
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
        "label": "全国房地产景气指数", "source": "AkShare/NBS", "frequency": "monthly",
        "metrics": {"value": {"label": "全国房地产景气指数", "unit": "index"}},
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
        "label": "生猪市场价格指数", "source": "AkShare/行情宝", "frequency": "weekly", "quality": "industry",
        "metrics": {
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
        "label": "主要央行政策利率", "source": "AkShare/金十数据", "frequency": "event", "quality": "aggregated",
        "metrics": {
            "usa": {"label": "美联储政策利率", "unit": "%"},
            "eur": {"label": "欧洲央行政策利率", "unit": "%"},
            "jpy": {"label": "日本央行政策利率", "unit": "%"},
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
