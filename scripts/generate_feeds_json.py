import configparser
import json
import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    config = configparser.ConfigParser()
    ini_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'default.ini')
    
    if not os.path.exists(ini_path):
        print(f"Error: {ini_path} not found")
        return

    config.read(ini_path, encoding='utf-8')
    
    feeds = []
    
    # Process Journals
    if 'paper.journals' in config:
        for title, url in config['paper.journals'].items():
            feeds.append({
                'title': title,
                'url': url,
                'type': 'journal'
            })
            
    # Process Researchers
    if 'paper.researchers' in config:
        for title, url in config['paper.researchers'].items():
            feeds.append({
                'title': title,
                'url': url,
                'type': 'researcher'
            })
            
    # Output
    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'feeds.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(feeds, f, indent=2, ensure_ascii=False)
        
    print(f"Generated {out_path} with {len(feeds)} feeds.")

if __name__ == "__main__":
    main()
