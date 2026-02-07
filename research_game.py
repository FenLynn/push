import sys
import os
import pandas as pd

# Mock the cloud import if possible, or adjust path
sys.path.append(os.path.join(os.getcwd(), '..', '..'))
try:
    from cloud import get_game_schedule
except ImportError:
    # If cloud is not found relative to here, try adding the root
    sys.path.append('/nfs/python/push')
    from cloud import get_game_schedule

games = ['王者荣耀', 'DOTA2', 'S15', 'KPL', '英雄联盟', 'LOL', 'LCK', 'LPL']

try:
    print("Fetching game schedule...")
    schedule = get_game_schedule(games)
    print(f"Type: {type(schedule)}")
    if hasattr(schedule, 'get_all_game_info'):
        df = schedule.get_all_game_info()
        print("Dataframe Head:")
        print(df.head().to_string())
        print("Columns:", df.columns)
        
        print("\nSample Data for Today:")
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        print(df[df['date'] == today].to_string())
    else:
        print("Schedule object structure:", dir(schedule))

except Exception as e:
    print(f"Error: {e}")
