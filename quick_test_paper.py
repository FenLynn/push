import sys
import os
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources.paper.source import PaperSource

def run_test():
    source = PaperSource()
    
    # Mock data
    today_info = {
        "today": datetime.now().strftime("%Y-%m-%d"),
        "journals": 3,
        "articles_sum": 5,
        "is_first_page": True,
        "paper": [
            {
                "journal": "陶汝茂",
                "type": "researcher",
                "articles_nu": 1,
                "data": [
                    {
                        "title": "High-power fiber laser with narrow linewidth and high beam quality based on XT fiber",
                        "link": "http://example.com/1",
                        "is_include_keyword": False,
                        "keywords": [],
                        "summary": "This is a summary of the researcher article.",
                        "global_idx": 1
                    }
                ]
            },
            {
                "journal": "Optics Express",
                "type": "journal",
                "articles_nu": 2,
                "data": [
                    {
                        "title": "Demonstration of a 5kW monolithic fiber laser oscillator with high instability threshold",
                        "link": "http://example.com/2",
                        "is_include_keyword": True,
                        "keywords": ["fiber", "laser"],
                        "summary": "AI Summary: This paper demonstrates a 5kW fiber laser...",
                        "global_idx": 2
                    },
                    {
                        "title": "A normal article without keywords",
                        "link": "http://example.com/3",
                        "is_include_keyword": False,
                        "keywords": [],
                        "summary": "",
                        "global_idx": 3
                    }
                ]
            },
            {
                "journal": "Chinese Optics Letters",
                "type": "journal",
                "articles_nu": 2,
                "data": [
                    {
                        "title": "Very long title to test the floating behavior of the keyword tags at the end of the line making sure it wraps correctly if needed",
                        "link": "http://example.com/4",
                        "is_include_keyword": True,
                        "keywords": ["narrow linewidth"],
                        "summary": "",
                        "global_idx": 4
                    },
                     {
                        "title": "Another article with keyword",
                        "link": "http://example.com/5",
                        "is_include_keyword": True,
                        "keywords": ["TMI"],
                        "summary": "",
                        "global_idx": 5
                    }
                ]
            }
        ]
    }

    html = source._generate_html(today_info)
    
    out_path = "/nfs/python/push/output/paper/latest.html"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Generated test HTML at: {out_path}")
    print(f"File size: {len(html)} bytes")

if __name__ == "__main__":
    run_test()
