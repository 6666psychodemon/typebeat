import scrapetube
import sqlite3
import time
import re
import random
from datetime import datetime, timedelta

def get_absolute_date(relative_text, scrape_date_str):
    """Upgraded Date Engine: Immune to View Count Hijacking"""
    if re.match(r"\d{4}-\d{2}-\d{2}", str(relative_text)):
        return relative_text

    try:
        scrape_date = datetime.strptime(scrape_date_str, "%Y-%m-%d")
    except:
        scrape_date = datetime.now()

    ts = str(relative_text).lower()
    
    # NEW REGEX: Forces the number to be immediately followed by a unit of time
    match = re.search(r"(\d+)\s*(year|yr|month|mo|week|wk|day|hour|min|sec)", ts)
    
    if not match: 
        return scrape_date.strftime("%Y-%m-%d")
    
    n = int(match.group(1))
    unit = match.group(2)
    
    days = 0
    if unit in ['year', 'yr']: days = n * 365
    elif unit in ['month', 'mo']: days = n * 30
    elif unit in ['week', 'wk']: days = n * 7
    elif unit == 'day': days = n
    # hours/mins/secs default to 0 days (today)
        
    actual_date = scrape_date - timedelta(days=days)
    return actual_date.strftime("%Y-%m-%d")

def extract_views(vid):
    v_text = vid.get('viewCountText', {}).get('simpleText') or "0"
    raw_text = v_text.lower().replace(',', '').replace(' ', '').replace('\xa0', '')
    multipliers = {'k': 1000, 'm': 1000000}
    multiplier = 1
    for key, val in multipliers.items():
        if key in raw_text:
            multiplier = val
            break
    nums = re.findall(r"(\d+\.?\d*)", raw_text)
    try: return int(float(nums[0]) * multiplier) if nums else 0
    except: return 0

def run_harvest():
    conn = sqlite3.connect("typebeats.db")
    cursor = conn.cursor()
    
    # Ensure the 10-column schema is ready
    cursor.execute('''CREATE TABLE IF NOT EXISTS beats 
        (video_id TEXT PRIMARY KEY, title TEXT, artist_style TEXT, 
        channel_name TEXT, url TEXT, views INTEGER, 
        published_time TEXT, scraped_at TEXT, genre TEXT, is_free INTEGER)''')

    try:
        with open("queries.txt", "r") as f:
            queries = [line.strip() for line in f.readlines()]
        random.shuffle(queries)
    except: 
        print("❌ Run generate_queries.py first!")
        return

    for q in queries:
        print(f"📡 Digging: {q}")
        consecutive_knowns = 0
        
        try:
            videos = scrapetube.get_search(q, limit=100)
            
            for vid in videos:
                video_id = vid['videoId']
                
                # --- THE CIRCUIT BREAKER ---
                cursor.execute("SELECT views FROM beats WHERE video_id=?", (video_id,))
                existing = cursor.fetchone()
                
                if existing:
                    consecutive_knowns += 1
                    # Update views quickly without rewriting the whole row
                    new_views = extract_views(vid)
                    cursor.execute("UPDATE beats SET views=?, scraped_at=? WHERE video_id=?", 
                                   (new_views, datetime.now().strftime("%Y-%m-%d"), video_id))
                    
                    if consecutive_knowns >= 3:
                        print("   ⏭️ Reached known territory. Skipping to next query.")
                        break 
                    continue 
                
                consecutive_knowns = 0
                
                title = vid['title']['runs'][0]['text']
                
                # Filter out anything that isn't explicitly a type beat
                if "type beat" not in title.lower():
                    continue
                
                is_free = 1 if "free" in title.lower() else 0
                views = extract_views(vid)
                
                if 0 < views <= 100000:
                    clean_style = q.replace('intitle:"type beat"', '').strip()
                    clean_style = re.sub(r'(after|before):\d{4}-\d{2}-\d{2}', '', clean_style).strip()
                    
                    # --- THE DATE FIX ---
                    pub_time_raw = vid.get('publishedTimeText', {}).get('simpleText') or "Unknown"
                    scrape_date_str = datetime.now().strftime("%Y-%m-%d")
                    actual_pub_date = get_absolute_date(pub_time_raw, scrape_date_str)
                    
                    cursor.execute('''INSERT OR REPLACE INTO beats 
                        (video_id, title, artist_style, channel_name, url, views, published_time, scraped_at, is_free) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (video_id, title, clean_style, 
                         vid['longBylineText']['runs'][0]['text'], f"https://youtube.com/watch?v={video_id}", 
                         views, actual_pub_date, scrape_date_str, is_free))
            
            conn.commit()
        except KeyboardInterrupt: 
            print("\n🛑 Manual stop received.")
            break
        except Exception as e: 
            continue
    
    conn.close()
    print("✅ Harvest complete.")

if __name__ == "__main__": 
    run_harvest()