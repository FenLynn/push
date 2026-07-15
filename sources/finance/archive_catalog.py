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
    "lpr": {
        "label": "贷款市场报价利率", "source": "AkShare/PBOC", "frequency": "monthly",
        "metrics": {
            "lpr1y": {"label": "LPR 1年期", "unit": "%"},
            "lpr5y": {"label": "LPR 5年期以上", "unit": "%"},
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
    "realestate": {
        "label": "全国房地产景气指数", "source": "AkShare/NBS", "frequency": "monthly",
        "metrics": {"value": {"label": "全国房地产景气指数", "unit": "index"}},
    },
}
