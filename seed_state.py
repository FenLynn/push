import json
try:
    with open('/tmp/stock_state.json', 'w') as f:
        json.dump({'last_total': 18000.0, 'date': '2026-02-11'}, f)
except Exception as e:
    print(e)
