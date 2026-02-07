
import requests
import re
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ShowStart")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.showstart.com/'
}

def check_event(event_id):
    url = f"https://www.showstart.com/event/{event_id}"
    logger.info(f"Fetching Event: {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            html = resp.text
            # Look for other event links?
            # Or look for Artist ID
            artist_id_match = re.search(r'artist/(\d+)', html)
            if artist_id_match:
                logger.info(f"Found Artist ID: {artist_id_match.group(1)}")
            
            # Look for tour list? usually in "related-events" or similar?
            # Naive search for Xi'an (encoded or raw)
            if "西安" in html:
                logger.info("Found '西安' in page content!")
                # Extract surrounding links
                matches = re.findall(r'<a[^>]*href=["\'](/event/\d+)["\'][^>]*>.*?西安.*?</a>', html, re.DOTALL)
                for m in matches:
                    logger.info(f"Found Xi'an Event Link: {m}")
            
            # Save dump
            with open("debug_tour_dump.html", "w") as f:
                f.write(html)
        else:
            logger.error(f"Failed: {resp.status_code}")
    except Exception as e:
        logger.error(str(e))

if __name__ == "__main__":
    # check_event(287957) # Hormone Miss Chengdu
    
    # Step 2: Check Artist Page
    artist_url = "https://www.showstart.com/artist/4386"
    logger.info(f"Fetching Artist: {artist_url}")
    try:
        resp = requests.get(artist_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            html = resp.text
            # Find Xi'an event
            # Look for /event/XXXXX
            # And checking if it contains "西安"
            # Since HTML might be separate items, let's dump and grep or use regex
            # Regex for event link
            matches = re.finditer(r'<a[^>]*href=["\'](/event/(\d+))["\'][^>]*>(.*?)</a>', html, re.DOTALL)
            found_xian = False
            for m in matches:
                link, eid, text = m.groups()
                # Clean text a bit
                clean_text = re.sub(r'\s+', '', text)
                if "西安" in clean_text or "西安" in html: # searching context is hard without soup
                    # Just try to fetch all events? No.
                    pass
            
            # Better: Regex nearest "西安"
            if "西安" in html:
                 # Find the event ID associated with Xi'an
                 # usually structure is ... href="/event/12345" ... city ... Xi'an ...
                 # Or just dump and I will read it.
                 with open("debug_artist_dump.html", "w") as f:
                     f.write(html)
                 logger.info("Saved artist dump.")
                 
                 # Try to extract simplisticly
                 # Assuming list of events.
                 # Let's just grep the file in next step if this works.
                 pass
        else:
             logger.error(f"Artist fetch failed: {resp.status_code}")
    except Exception as e:
        logger.error(str(e))
