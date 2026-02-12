import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.d1_client import D1Client

load_dotenv()
d1 = D1Client()
res = d1.query("SELECT COUNT(*) as count FROM articles")
if res.get('success'):
    c = res['data'][0]['results'][0]['count'] if 'results' in res['data'][0] else res['data'][0]['count']
    print(f"Current Articles in D1: {c}")
else:
    print(f"Query Failed: {res.get('error')}")
